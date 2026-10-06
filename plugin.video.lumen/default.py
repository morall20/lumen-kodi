import os
import sys
import xbmcaddon

ADDON = xbmcaddon.Addon()
sys.path.insert(0, os.path.join(ADDON.getAddonInfo('path'), 'resources', 'lib'))
from app import run
run(sys.argv)
