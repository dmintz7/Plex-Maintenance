from flask import Flask, request, make_response
from plexapi.server import PlexServer
from logging.handlers import RotatingFileHandler
import trakt, os, subprocess, logging, sys, config, time
trakt.core.CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".pytrakt.json")
import trakt.movies, trakt.tv, trakt.sync, trakt.users, trakt.core

plex = PlexServer(config.plex_host, config.plex_api)
app = Flask(__name__)

logger = logging.getLogger('root')
formatter = logging.Formatter('%(asctime)s - %(levelname)10s - %(module)15s:%(funcName)30s:%(lineno)5s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(formatter)	
logger.addHandler(consoleHandler)
logging.getLogger("requests").setLevel(logging.INFO)
logger.setLevel(config.log_level.upper())
fileHandler = RotatingFileHandler(config.log_folder + "plex-maintenance.log", maxBytes=1024 * 1024 * 2, backupCount=1)
fileHandler.setFormatter(formatter)
logger.addHandler(fileHandler)

@app.route('/', methods=['POST'])
def api_command():
	json_text = request.get_json()
	logger.debug("Received API Command - %s" % json_text)
	(section_id, event, directory, title) = parese_json(json_text)
	if event == 'Test':
		get_plex_duplicates()
		section_id = None
		logger.info("Test Command Received")

	if section_id is not None:
		try:
			if config.remote_sodarr: directory = os.path.abspath(directory.replace(config.from_path, config.to_path).replace("\\","/"))
			command = '%s --scan --refresh --section %s --directory "%s"' % (config.plex_media_scanner_path, section_id, directory)
			logger.info("Adding %s to Plex" % title)
			process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
			process.wait()
			
			if event == 'Download':
				if json_text['isUpgrade']:
					get_plex_duplicates()
				plex_video = None
				for x in range(0, 5):
					if plex_video is not None: break
					plex_video = getPlexVideo(json_text)
				
				if not plex_video.isWatched:
					if plex_video.type == "movie":
						last_watched = movie_last_watched(plex_video.guid)
					elif plex_video.type == "episode":
						last_watched = episode_last_watched(plex_video.guid)
					else:
						last_watched = None	
						
					logger.info(last_watched)
					if last_watched is not None:
						plex_video.markWatched()
						logger.info("Last Watched in Trakt at %s. Marking as Watched in Plex" % last_watched)
			elif event == 'Rename':
				get_plex_duplicates()
			
		except Exception as e:
			logger.error('Error on line {} - {} - {}'.format(type(e).__name__, sys.exc_info()[-1].tb_lineno, e))
	return make_response("", 200)

def create_plex_title(video):
	if video.type == "movie":
		try:
			title = "%s (%s)" % (video.title, video.originallyAvailableAt.strftime("%Y"))
		except:
			title = video.title
	else:
		title = "%s - %s - %s" % (video.grandparentTitle, video.parentTitle, video.title)
	return title

def get_plex_duplicates():
	exists = []
	missing = []
	duplicates = []
	logger.debug("Checking for Duplicates")
	for section in plex.library.sections():
		if section.TYPE in ('movie'):
			duplicates = duplicates + section.search(duplicate=True)
		elif section.TYPE in ('show'):
			duplicates = duplicates + section.searchEpisodes(duplicate=True)
	for dup in duplicates:
		try:
			if len(dup.locations) > 1:
				parts = create_media_lists(dup)
				for media, video in parts:
					if os.path.exists(video.file):
						logger.debug("Adding %s to existing" % video.file)
						exists.append(create_plex_title(dup))
					else:
						logger.debug("Adding %s to missing" % video.file)
						missing.append((media, video, dup))
		except:
			pass

	if len(missing) > 0:
		for media, video, dup in missing:
			try:
				if create_plex_title(dup) in exists:
					logger.info("File (%s) missing from Plex Database" % video.file)
					if not os.path.exists(video.file): media.delete()
			except:
				pass
				
def create_media_lists(movie):
	try:
		patched_items = []
		for zomg in movie.media:
			zomg._initpath = movie.key
			patched_items.append(zomg)
		zipped = zip(patched_items, movie.iterParts())
		parts = sorted(zipped, key=lambda i: i[1].size if i[1].size else 0, reverse=True)
		return parts
	except:
		return None
		
def episode_last_watched(guid):
	(id, provider, season, episode) = get_provider_id("tv", guid)
	trakt_user = trakt.users.User(config.trakt_username)
	watched = trakt_user.watched_shows
	for x in watched:
		if str(x.ids['ids'][provider]) == str(id):
			for z in x.seasons:
				if z['number'] == int(season):
					for y in z['episodes']:
						if y['number'] == int(episode):
							return y['last_watched_at']
				
def movie_last_watched(guid):
	(id, provider) = get_provider_id("movie", guid)
	trakt_user = trakt.users.User(config.trakt_username)
	watched = trakt_user.watched_movies
	for x in watched:
		if str(x.ids['ids'][provider]) == str(id): return x.last_watched_at

def get_provider_id(type, guid):
	if type == "movie":
		id = guid[guid.find("//")+2:guid.find("?", guid.find("//")+2)]
		if 'imdb' in guid:
			x = guid.split('//')[1]
			x = x.split('?')[0]
			provider = 'imdb'
		elif 'themoviedb' in guid:
			x = guid.split('//')[1]
			x = x.split('?')[0]
			provider = 'tmdb'
		return (id, provider)
	elif type == "tv":
		id = guid[guid.find("//")+2:guid.find("?", guid.find("//")+2)].split("/")[0]
		try:
			season = guid[guid.find("//")+2:guid.find("?", guid.find("//")+2)].split("/")[1]
			episode = guid[guid.find("//")+2:guid.find("?", guid.find("//")+2)].split("/")[2]
		except:
			season = None
			episode = None
			
		if 'thetvdb' in guid:
			x = guid.split('//')[1]
			x = x.split('?')[0]
			provider = 'tvdb'
		elif 'themoviedb' in guid:
			x = guid.split('//')[1]
			x = x.split('?')[0]
			provider = 'tmdb'
		return (id, provider, season, episode)
		
def getPlexVideo(json_text):
	try:
		title = json_text['movie']['title']
		filename = json_text['movieFile']['relativePath']
	except:
		title = json_text['episodes'][0]['title']
		filename = json_text['episodeFile']['relativePath']
	
	time.sleep(5)
	for x in plex.library.search(title=title):
		for y in x.locations:
			if y.split("/")[-1] == filename.split("\\")[-1]:
				return x

def parese_json(json_text):
	try:
		event = json_text['eventType']
		if event == 'Test':
			section_id = 1
			directory = "Test"
			title = "Test"
		elif 'movie' in json_text:
			section_id = config.movie_section_id
			directory = json_text['movie']['folderPath']
			if event == 'Rename':
				title = json_text['movie']['title']
			else:
				title = "%s (%s) - %s" % (json_text['movie']['title'], json_text['remoteMovie']['year'], json_text['movieFile']['quality'])
		elif 'episode' in json_text:
			section_id = config.tv_section_id
			directory = json_text['series']['path']
			show_title = json_text['series']['title']
			if event == 'Rename':
				title = show_title
			else:
				episode_title = json_text['episodes'][0]['title']
				season = json_text['episodes'][0]['seasonNumber']
				episode = json_text['episodes'][0]['episodeNumber']
				quality = json_text['episodes'][0]['quality']
				title = "%s - S%sE%s - %s - %s" % (show_title, season, episode, episode_title, quality)
		else:
			section_id = 0
	except Exception as e:
		logger.error('Error on line {} - {} - {}'.format(type(e).__name__, sys.exc_info()[-1].tb_lineno, e))
		section_id = 0
		raise
	
	if int(section_id) > 0:
		return (section_id, event, directory, title)
	else:
		return None