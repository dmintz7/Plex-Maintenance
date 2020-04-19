from flask import Flask, request, make_response
from plexapi.server import PlexServer
from logging.handlers import RotatingFileHandler

import os, subprocess, logging, sys
import config

plex = PlexServer(config.plex_host, config.plex_api)
app = Flask(__name__)

logger = logging.getLogger('root')
formatter = logging.Formatter('%(asctime)s - %(levelname)10s - %(module)15s:%(funcName)30s:%(lineno)5s - %(message)s')
logger = logging.getLogger()
logger.setLevel(logging.INFO)
consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setFormatter(formatter)	
logger.addHandler(consoleHandler)
logging.getLogger("requests").setLevel(logging.WARNING)
logger.setLevel("INFO")
fileHandler = RotatingFileHandler(config.log_folder + "plex-maintenance.log", maxBytes=1024 * 1024 * 2, backupCount=1)
fileHandler.setFormatter(formatter)
logger.addHandler(fileHandler)

@app.route('/', methods=['POST'])
def api_command():
	json_text = request.get_json()
	logger.info("Received API Command - %s" % json_text)
	try:
		directory = json_text['series']['path']
		section_id = config.tv_section_id
	except KeyError:
		directory = json_text['movie']['folderPath']
		section_id = config.movie_section_id
	except:
		section_id = 0
		directory = False

	if int(section_id) > 0:
		try:
			if config.remote_sodarr: directory = os.path.abspath(directory.replace(config.from_path, config.to_path).replace("\\","/"))
			command = '%s --scan --refresh --section %s --directory "%s"' % (config.plex_media_scanner_path, section_id, directory)
			logger.info("Scanning %s" % directory)
			process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
			process.wait()
			if json_text['eventType'] == 'Download':
				if json_text['isUpgrade']:
					logger.info("Checking for Duplicates")
					get_plex_duplicates()
			if json_text['eventType'] == 'Rename':
				logger.info("Checking for Duplicates")
				get_plex_duplicates()
		except:
			pass
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
						exists.append(create_plex_title(dup))
					else:
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