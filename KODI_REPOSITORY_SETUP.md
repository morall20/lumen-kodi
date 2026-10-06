# Connect Kodi to Lumen updates

## Current prerequisite

This repository was created private. The standard Kodi repository ZIP below needs its distribution files accessible without a GitHub login. Until the owner approves public hosting, Kodi will return an access error/404 when refreshing this feed. A GitHub browser login does not authenticate Kodi. Do not embed passwords or personal access tokens in the ZIP.

## Install once on each device, after the feed is public

1. Download `repository.lumen-1.0.0.zip`. Keep the ZIP intact and copy it to the Shield or phone's Downloads folder.
2. Kodi → Settings → System → Add-ons → enable **Unknown sources** for this personal repository.
3. Kodi → Add-ons → package/box icon → **Install from zip file** → select the repository ZIP.
4. Select **Install from repository → Lumen Repository → Video add-ons → Lumen → Install**.
5. If you already installed the development ZIP directly, install Lumen from this repository at the same version to associate the installation with the feed; confirm its Origin shows Lumen Repository if Kodi offers that field.
6. Open Lumen's add-on Information page and enable **Auto-update**. Under Settings → System → Add-ons, set Updates to **Install updates automatically** if desired. If Kodi's update policy limits updates to official repositories, select the setting permitting updates from installed repositories you trust.
7. To request a refresh, highlight Lumen Repository under My add-ons → Add-on repository, open its context menu and choose **Check for updates**. Then check available updates or Lumen → Information → Versions.

Kodi updates on its scheduled checks or a manual check; it does not synchronize every Git commit immediately. Only new numbered packages in `repo/addons.xml` qualify. Each device keeps its own Lumen account credentials and settings; the repository does not sync accounts or device preferences.

## Direct installation while private

Sign in as `morall20` at https://github.com/morall20/lumen-kodi, open `repo/plugin.video.lumen/`, download the versioned ZIP, copy it to the device, then use **Install from zip file**. Repeat manually for newer versions until an accessible feed is enabled.

## Limitations and recovery

Neither ZIP has been installed on Kodi hardware in this build environment. Start with the Shield TV Pro and preserve your working setup. If an update has a regression, download an earlier retained package and install it manually, then disable Auto-update until a higher-version fix is published. Re-enabling Auto-update before the fix will select the newer broken version again.

The separate CocoScrapers module and service account setup are covered in `plugin.video.lumen/INSTALL.md`. Do not upload Kodi userdata, `accounts.json`, API keys, signed playback URLs, database files or local settings to GitHub.
