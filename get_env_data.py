from os import path
import trakt, trakt.core, config

trakt.core.CONFIG_PATH = path.join(path.dirname(path.abspath(__file__)), ".pytrakt.json")
trakt.APPLICATION_ID = '65370'
trakt.core.AUTH_METHOD="OAUTH"
trakt.init(config.trakt_username, store=True)
print("You are now logged into Trakt. Your Trakt credentials have been added in .pytrakt.json file.")
print("You can enjoy sync! \nCheck config.json to adjust settings.")
print("If you want to change Trakt account, just edit or remove .pytrakt.json file.")