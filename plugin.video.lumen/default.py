import os
import sys
import xbmcaddon
import xbmc
import xbmcgui
import xbmcplugin
import router

ADDON = xbmcaddon.Addon()
sys.path.insert(0, os.path.join(ADDON.getAddonInfo('path'), 'resources', 'lib'))
from diagnostics import failure_report

try:
    action, params = router.parse(sys.argv)
    if action == 'settings':
        # Settings remain accessible even when dashboard initialization fails.
        ADDON.openSettings()
        if len(sys.argv) > 1 and str(sys.argv[1]).isdigit():
            xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=True)
    else:
        from app import run
        run(sys.argv)
except Exception as error:
    report = failure_report(error, 'launch')
    xbmc.log(report, xbmc.LOGERROR)
    xbmcgui.Dialog().textviewer('Lumen launch failed', report + '\n\nShare this report to diagnose the remaining failure. It excludes account credentials.')
    if len(sys.argv) > 1 and str(sys.argv[1]).isdigit():
        xbmcplugin.endOfDirectory(int(sys.argv[1]), succeeded=False)
