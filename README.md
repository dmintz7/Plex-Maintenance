# Plex Maintenance
 
Scans New Media to Plex Media Server. 

If duplicates are discovered and the one or more of the files no longer exists, it will remove the non-exist media from Plex

Can work with Library Scans disabled in Plex Server Settings

Allow Media Delation MUST be enabled in Plex Server Settings


Created to work with Sonarr and Radarr

Under Settings - Connections
    Create a New Webhook
	Enable On Download, On Upgrade and On Rename
	URL = URL-OF-HOST:32500
	METHOD = POST