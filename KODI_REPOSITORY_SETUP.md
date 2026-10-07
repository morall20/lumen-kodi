# Connect Kodi to Lumen updates

## Public update feed

The GitHub repository is public, and the standard repository ZIP points to its `main/repo/` feed. No GitHub login is needed by Kodi. Download and install the repository ZIP once per device, then use Install from repository. Lumen 0.2.0 is the current development package; live device verification is still pending.

## Install once on each device

1. Download `repository.lumen-1.0.1.zip`. Keep the ZIP intact and copy it to the Shield or phone's Downloads folder.
2. Kodi → Settings → System → Add-ons → enable **Unknown sources** for this personal repository.
3. Kodi → Add-ons → package/box icon → **Install from zip file** → select the repository ZIP.
4. Select **Install from repository → Lumen Repository → Video add-ons → Lumen → Install**.
5. If you already installed the development ZIP directly, install Lumen from this repository at the same version to associate the installation with the feed; confirm its Origin shows Lumen Repository if Kodi offers that field.
6. Open Lumen's add-on Information page and enable **Auto-update**. Under Settings → System → Add-ons, set Updates to **Install updates automatically** if desired. If Kodi's update policy limits updates to official repositories, select the setting permitting updates from installed repositories you trust.
7. To request a refresh, highlight Lumen Repository under My add-ons → Add-on repository, open its context menu and choose **Check for updates**. Then check available updates or Lumen → Information → Versions.

Kodi updates on its scheduled checks or a manual check; it does not synchronize every Git commit immediately. Only new numbered packages in `repo/addons.xml` qualify. Each device keeps its own Lumen account credentials and settings; the repository does not sync accounts or device preferences.

## Direct installation and troubleshooting

You can also download a versioned Lumen ZIP from `repo/plugin.video.lumen/` and use Install from zip file. If the repository previously reported server not reached, restart Kodi and use its Check for updates command. If it still fails, capture the exact message and Kodi log; public visibility resolves authentication errors but does not rule out device DNS, firewall, network or installation problems.

## Limitations and recovery

Neither ZIP has been installed on Kodi hardware in this build environment. Start with the Shield TV Pro and preserve your working setup. If an update has a regression, download an earlier retained package and install it manually, then disable Auto-update until a higher-version fix is published. Re-enabling Auto-update before the fix will select the newer broken version again.

The separate CocoScrapers module and service account setup are covered in `plugin.video.lumen/INSTALL.md`. Do not upload Kodi userdata, `accounts.json`, API keys, signed playback URLs, database files or local settings to GitHub.

## Recover from a cached 0.1.1 listing

Install repository.lumen-1.0.1.zip over the older repository. It uses fresh catalog URLs while retaining the original add-on ID. Restart Kodi, select Lumen Repository → Check for updates, then open Lumen → Information → Versions and select 0.2.0 from Lumen Repository. If 0.2.0 is not offered, install its ZIP directly and report the installed repository version and exact error. The old 1.0.0 URLs are still generated for existing clients.
