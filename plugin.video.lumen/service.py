"""Playback observer; tracks only Lumen-launched playback."""
import hashlib
import json
import os
import queue
import sys
import time
import xbmc
import xbmcaddon
import xbmcgui

sys.path.insert(0,os.path.join(xbmcaddon.Addon('plugin.video.lumen').getAddonInfo('path'),'resources','lib'))
from runtime import read, write, flag, credential
from accounts import trakt
from catalog import media_key
from modules import release_radar

events=queue.Queue(maxsize=30)

class Observer(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.media=None
        self.position=0
        self.total=0
        self.last_saved=0

    def event(self,kind):
        if self.media:
            try:
                events.put_nowait((kind,dict(self.media),self.position,self.total))
            except queue.Full:
                pass

    def onAVStarted(self):
        self.media=None
        w=xbmcgui.Window(10000)
        pending=w.getProperty('lumen.playback')
        w.clearProperty('lumen.playback')
        try:
            data=json.loads(pending)
            digest=hashlib.sha256(self.getPlayingFile().encode('utf-8')).hexdigest()
            if time.time()-data['time']<60 and digest==data['digest']:
                self.media=data['media']
                self.position=0
                self.total=self.getTotalTime()
                self.event('start')
        except (ValueError,KeyError,RuntimeError):
            pass

    def onPlayBackPaused(self):
        self.event('pause')

    def onPlayBackResumed(self):
        self.event('start')

    def onPlayBackStopped(self):
        self.event('stop')
        self.media=None

    def onPlayBackEnded(self):
        self.position=self.total
        self.event('stop')
        self.media=None

player=Observer()
monitor=xbmc.Monitor()
radar_worker=None
radar_checked=0
while not monitor.waitForAbort(.5):
    if time.monotonic()-radar_checked>60 and (radar_worker is None or not radar_worker.is_alive()):
        radar_checked=time.monotonic()
        radar_worker=release_radar.start(cancel=monitor.abortRequested)
    if player.media and player.isPlayingVideo():
        try:
            player.position=player.getTime()
            player.total=player.getTotalTime()
            if time.time()-player.last_saved>10:
                write('resume:'+media_key(player.media),{'position':player.position,'total':player.total,'updated':time.time()})
                player.last_saved=time.time()
        except RuntimeError:
            pass
    while not events.empty():
        kind,media,position,total=events.get_nowait()
        write('resume:'+media_key(media),{'position':0 if total and position/total>.9 else position,'total':total,'updated':time.time()})
        if flag('trakt.scrobble') and credential('trakt').get('access_token') and total>0:
            body={'movie' if media['type']=='movie' else 'episode':{'ids':{'tmdb':media['id']}},
                  'progress':min(100,max(0,position/total*100)), 'app_version':xbmcaddon.Addon('plugin.video.lumen').getAddonInfo('version')}
            try:
                trakt('scrobble/'+kind,'POST',body)
            except Exception:
                # Local progress remains; do not replay old scrobbles over newer device state.
                write('sync_status',{'failed':True,'time':time.time()})
