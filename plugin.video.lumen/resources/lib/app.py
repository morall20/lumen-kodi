import json
import hashlib
import os
import re
import sys
import threading
import time
from urllib.parse import urlencode, parse_qs, quote
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
from runtime import ADDON, read, write, credential, request, ApiError, preferences, setting, flag, clear_search
from accounts import SERVICES, active_services, validate, resolve, tmdb, mdb, trakt
import catalog
import providers
import activation
import framework
import router
from diagnostics import failure_report

DIALOG = xbmcgui.Dialog()
MONITOR = xbmc.Monitor()

def notice(message):
    DIALOG.notification('Lumen',message,ADDON.getAddonInfo('icon'),4000)

def safe_label(value):
    return str(value).replace('[','(').replace(']',')')[:500]

def url(action, **kwargs):
    return 'plugin://plugin.video.lumen/?'+urlencode(dict(kwargs,action=action))

def package_media(media):
    # Only catalog identity/metadata goes into routes, never a signed playback URL.
    return json.dumps(media,separators=(',',':'))

def item(media):
    label = safe_label(media['title'])
    if media['type']=='episode':
        label = '%s · S%02dE%02d · %s'%(safe_label(media.get('show_title','')),int(media['season']),int(media['episode']),label)
    li = xbmcgui.ListItem(label, label2=media.get('badge',''))
    tag = li.getVideoInfoTag()
    tag.setTitle(media['title'])
    tag.setPlot(media.get('plot',''))
    tag.setMediaType({'tv':'tvshow','season':'season','episode':'episode'}.get(media['type'],'movie'))
    try:
        tag.setYear(int(media.get('year',0) or 0))
    except ValueError:
        pass
    if media['type']=='episode':
        tag.setSeason(int(media['season']))
        tag.setEpisode(int(media['episode']))
        tag.setTvShowTitle(media.get('show_title',''))
    li.setArt({'poster':media.get('poster',''), 'thumb':media.get('poster','') or ADDON.getAddonInfo('icon'),
               'fanart':media.get('fanart','') or os.path.join(ADDON.getAddonInfo('path'),'resources/media/fanart.png')})
    return li

def trailer(media):
    kind='tv' if media['type'] in ('episode','tv','season') else 'movie'
    videos=tmdb('%s/%s/videos'%(kind,media.get('show_id',media['id']))).get('results',[])
    videos=[v for v in videos if v.get('site')=='YouTube' and re.fullmatch(r'[A-Za-z0-9_-]{6,30}',v.get('key',''))]
    if not videos:
        DIALOG.ok('Trailer sources','No supported trailer sources were returned for this title.')
        return
    index=DIALOG.select('Select trailer source', ['%s · %s · %s · %sp'%(safe_label(v['name']),v.get('type','Video'),v.get('iso_639_1',''),v.get('size','?')) for v in videos])
    if index<0:
        return
    try:
        xbmcaddon.Addon('plugin.video.youtube')
    except RuntimeError:
        DIALOG.ok('YouTube required','Install and configure the YouTube add-on from Kodi’s official repository to play these trailers. Lumen will not install it automatically.')
        return
    xbmc.Player().play('plugin://plugin.video.youtube/play/?video_id='+videos[index]['key'])

def choose_file(files):
    if not files:
        DIALOG.ok('Matching file unavailable','No video file matched this selection. Episode packs require an exact episode filename match.')
        return None
    if len(files)==1:
        return files[0]
    i=DIALOG.select('Choose video file',[safe_label(x.get('path') or x.get('name','Video')) for x in files])
    return files[i] if i>=0 else None

def play_sources(media, fresh=False, options=False):
    prefs=preferences(media['type'])
    services=active_services()
    selected_modules=None
    if not services:
        DIALOG.ok('Connect a debrid service','Open Accounts to connect Real-Debrid, TorBox or Premiumize. AllDebrid account validation is available; its playback adapter is pending.')
        return
    if options:
        i=DIALOG.select('Rescrape options',['All enabled services','Choose services','Temporarily show unknown availability','Temporarily allow unknown resolution','Open saved quality settings','Choose source modules'])
        if i<0:
            return
        if i==1:
            selected=DIALOG.multiselect('Services',[SERVICES[s] for s in services],preselect=list(range(len(services))))
            if selected is None or not selected:
                return
            services=[services[x] for x in selected]
        elif i==2:
            prefs['ready_only']=False
        elif i==3:
            prefs['unknown_quality']=True
        elif i==5:
            module_names=[job[0] for job in providers.jobs(catalog.detail(media))]
            indices=DIALOG.multiselect('Modules for this rescrape',module_names,preselect=list(range(len(module_names))))
            if indices is None or not indices:
                return
            selected_modules=[module_names[n] for n in indices]
        elif i==4:
            ADDON.openSettings()
            prefs=preferences(media['type'])
    progress=xbmcgui.DialogProgress()
    progress.create('Lumen · sources','Searching enabled modules and checking services…')
    try:
        results,errors=catalog.sources(media,prefs,fresh=fresh,cancel=lambda:progress.iscanceled() or MONITOR.abortRequested(),services=services,selected_modules=selected_modules)
        canceled=progress.iscanceled()
    finally:
        progress.close()
    if canceled:
        return
    if not results:
        DIALOG.ok('No qualifying sources','Try Rescrape Options or adjust your filters. Unknown availability is not confirmed ready.\n'+'\n'.join(errors[:3]))
        return
    labels=['%s · %s · %s · %s · %s\n%s'%(SERVICES[s['service']],s['availability'].upper(),s['resolution'],s['source_type'],
             ('%.2f GB'%s['size_gb']) if s['size_gb'] else 'Size unknown',safe_label(s['name'])) for s in results]
    count=int(setting('shortlist','3'))
    shortlist=labels[:count]+(['More sources…'] if len(results)>count else [])
    selected=DIALOG.select('Recommended sources',shortlist)
    if selected==count and len(results)>count:
        selected=DIALOG.select('All eligible sources',labels)
    if selected<0:
        return
    source=results[selected]
    if source['service']=='ad':
        DIALOG.ok('AllDebrid development status','Account connection and account-torrent checks are present. AllDebrid playback is not yet implemented in this build. Select another service.')
        return
    try:
        link=resolve(source['service'],source,media,choose_file,lambda msg:DIALOG.yesno('Selected source',msg),MONITOR.waitForAbort)
        if not isinstance(link,str) or not link.startswith('https://'):
            if link:
                raise ApiError(0)
            return
        li=item(media)
        li.setPath(link)
        li.setProperty('IsPlayable','true')
        # Playback service reads this ephemeral property; no signed URL persisted.
        xbmcgui.Window(10000).setProperty('lumen.playback',json.dumps({'media':media,'time':time.time(),'digest':hashlib.sha256(link.encode('utf-8')).hexdigest()}))
        resume=read('resume:'+catalog.media_key(media),{})
        seconds=resume.get('position',0)
        if credential('trakt').get('access_token'):
            try:
                kind='movies' if media['type']=='movie' else 'episodes'
                for entry in trakt('sync/playback/'+kind):
                    raw=entry.get('movie') or entry.get('episode',{})
                    if raw.get('ids',{}).get('tmdb')==media['id']:
                        # Remote resume is a percentage; Kodi StartPercent uses it directly.
                        li.setProperty('StartPercent',str(entry['progress']))
                        seconds=0
                        break
            except ApiError:
                notice('Trakt resume unavailable; using local progress')
        if seconds>0 and DIALOG.yesno('Resume','Resume from %s minutes?'%int(seconds/60)):
            li.setProperty('StartOffset',str(seconds))
        xbmc.Player().play(link,li)
    except ApiError as err:
        DIALOG.ok('Source unavailable','This source could not be resolved. Try another source.\n'+str(err))

def context(media):
    if media['type'] in ('tv','season','collection'):
        if media['type']=='tv':
            trailer(media)
        else:
            notice('Open this group to select an individual video')
        return
    i=DIALOG.contextmenu(['Select sources','Select trailer source','Rescrape sources','Rescrape options…','Add/remove local watchlist','Add to Trakt watchlist'])
    if i==0:
        play_sources(media)
    elif i==1:
        trailer(media)
    elif i==2:
        play_sources(media,True)
    elif i==3:
        play_sources(media,True,True)
    elif i==4:
        saved=read('watchlist',[])
        key=catalog.media_key(media)
        if any(catalog.media_key(m)==key for m in saved):
            saved=[m for m in saved if catalog.media_key(m)!=key]
        else:
            saved.append(media)
        write('watchlist',saved)
        notice('Local watchlist updated')
    elif i==5:
        kind='shows' if media['type'] in ('tv','season') else 'episodes' if media['type']=='episode' else 'movies'
        trakt('sync/watchlist','POST',{kind:[{'ids':{'tmdb':media['id']}}]})
        notice('Trakt watchlist updated')

def connect(selection=None):
    rows=['TMDB catalog key','Trakt activation','MDBList API key']+[SERVICES[s]+' account' for s in SERVICES]+['Select MDBList/Trakt widget lists','Disconnect an account','Trakt application setup']
    i=selection if selection is not None else DIALOG.select('Lumen · Accounts',rows)
    if i<0:
        return
    if i==1:
        app=credential('trakt_app')
        if not app.get('client_id') or not app.get('client_secret'):
            DIALOG.ok('Trakt application setup','First choose Trakt application setup. Register a personal Lumen API app at trakt.tv/oauth/applications and enter its client ID and secret here, not in chat.')
            return
        progress=xbmcgui.DialogProgress()
        try:
            token=activation.activate_trakt(app,
                lambda verification,code:progress.create('Activate Trakt','Visit %s\nCode: %s'%(verification,code)),
                progress.iscanceled,MONITOR.waitForAbort)
            if token:
                credential('trakt',token)
                notice('Trakt connected')
        finally:
            progress.close()
        return
    if i==7:
        definitions=[]
        for service in ('mdb','trakt'):
            try:
                definitions.extend(catalog.list_definitions(service))
            except ApiError:
                pass
        if not definitions:
            DIALOG.ok('No lists available','Connect MDBList or Trakt and create a list in that service first.')
            return
        indices=DIALOG.multiselect('Select startup reference lists',[d['service'].upper()+' · '+safe_label(d['name']) for d in definitions])
        if indices is not None:
            write('selected_lists',[definitions[x] for x in indices])
            ADDON.setSetting('list_widgets','true')
        return
    if i==8:
        keys=['tmdb','trakt','mdb']+list(SERVICES)
        j=DIALOG.select('Disconnect',[s for s in keys if credential(s)])
        connected=[s for s in keys if credential(s)]
        if j>=0 and DIALOG.yesno('Disconnect','Remove %s credentials from this device?'%connected[j]):
            credential(connected[j],remove=True)
            # Avoid retained stale verified results from a disconnected service.
            write('availability',{})
        return
    if i==9:
        client=DIALOG.input('Your Lumen Trakt client ID')
        secret=DIALOG.input('Your Lumen Trakt client secret',option=xbmcgui.ALPHANUM_HIDE_INPUT)
        if client and secret:
            credential('trakt_app',{'client_id':client.strip(),'client_secret':secret.strip()})
        return
    key='tmdb' if i==0 else 'mdb' if i==2 else list(SERVICES)[i-3]
    if key=='ad':
        mode=DIALOG.select('AllDebrid activation',['Activate with PIN','Enter API key'])
        if mode<0:
            return
        if mode==0:
            pin=request('https://api.alldebrid.com/v4.1/pin/get',params={'agent':'Lumen'}).get('data',{})
            progress=xbmcgui.DialogProgress()
            progress.create('Activate AllDebrid','Visit %s\nCode: %s'%(pin['user_url'],pin['pin']))
            deadline=time.monotonic()+int(pin['expires_in'])
            try:
                while time.monotonic()<deadline and not progress.iscanceled():
                    if MONITOR.waitForAbort(5):
                        return
                    response=request('https://api.alldebrid.com/v4/pin/check','POST',params={'agent':'Lumen'},data={'check':pin['check'],'pin':pin['pin']},form=True)
                    data=response.get('data',{})
                    if data.get('apikey'):
                        validate('ad',data['apikey'])
                        credential('ad',{'token':data['apikey']})
                        notice('AllDebrid account connected; playback pending')
                        return
                    if response.get('status')!='success':
                        raise ApiError(400)
            finally:
                progress.close()
            return
    token=DIALOG.input(rows[i],option=xbmcgui.ALPHANUM_HIDE_INPUT).strip()
    if not token:
        return
    if key in SERVICES:
        validate(key,token)
    elif key=='tmdb':
        headers={'Authorization':'Bearer '+token} if len(token)!=32 else {}
        request('https://api.themoviedb.org/3/configuration',params={'api_key':token} if len(token)==32 else {},headers=headers)
    else:
        request('https://api.mdblist.com/user',params={'apikey':token})
    credential(key,{'token':token})
    notice(rows[i]+' connected')

def provider_setup():
    choice=DIALOG.select('Providers',['Select CocoScrapers providers','CocoScrapers settings','Register additional installed adapter','Enable/disable additional adapters'])
    if choice==0:
        try:
            # Explicit re-selection permits a reviewed new installed version.
            names=providers.coco_providers(allow_version_change=True)
        except Exception:
            DIALOG.ok('CocoScrapers required','Install CocoScrapers separately from its official repository, then return here. See INSTALL.md. No scraper is bundled or silently installed.')
            return
        selected=read('coco.providers',[])
        indices=DIALOG.multiselect('CocoScrapers providers',[safe_label(n) for n in names],preselect=[i for i,n in enumerate(names) if n in selected])
        if indices is not None:
            write('coco.providers',[names[i] for i in indices])
            write('coco.approved_version',xbmcaddon.Addon('script.module.cocoscrapers').getAddonInfo('version'))
    elif choice==1:
        xbmcaddon.Addon('script.module.cocoscrapers').openSettings()
    elif choice==2:
        addon_id=DIALOG.input('Installed adapter add-on ID')
        module=DIALOG.input('Adapter Python import name')
        if not re.fullmatch(r'[a-zA-Z0-9_.]+',addon_id or '') or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_.]*',module or ''):
            return
        addon=xbmcaddon.Addon(addon_id)
        if not DIALOG.yesno('Enable external code','Enable %s version %s? Installed Python modules run with Kodi permissions. Only enable code you have reviewed.'%(addon.getAddonInfo('name'),addon.getAddonInfo('version'))):
            return
        adapters=providers.registry()
        adapters=[a for a in adapters if a['addon_id']!=addon_id]
        adapters.append({'addon_id':addon_id,'module':module,'enabled':True,'version':addon.getAddonInfo('version')})
        write('adapters',adapters)
    elif choice==3:
        adapters=providers.registry()
        indices=DIALOG.multiselect('Enabled adapters',[a['addon_id'] for a in adapters],preselect=[i for i,a in enumerate(adapters) if a['enabled']])
        if indices is not None:
            for i,a in enumerate(adapters):
                a['enabled']=i in indices
            write('adapters',adapters)

class Home(xbmcgui.WindowXMLDialog):
    def onInit(self):
        try:
            self.initialize()
        except Exception as error:
            self.startup_error = failure_report(error, 'dashboard initialization')
            xbmc.log(self.startup_error, xbmc.LOGERROR)
            self.closed = True
            self.close()

    def initialize(self):
        self.media=[]
        self.running=False
        self.closed=False
        self.tab=10
        self.history=[]
        self.getControl(2).setLabel('LUMEN  /  NEWLY AVAILABLE')
        self.render(catalog.available(preferences(),today=True))
        self.setFocusId(100 if self.media else 20)
        if flag('refresh_startup',True):
            self.refresh()

    def status(self,text):
        if not self.closed:
            self.getControl(3).setLabel(safe_label(text))

    def render(self,media,remember=False):
        if self.closed:
            return
        control=self.getControl(100)
        if remember:
            self.history.append((list(self.media),control.getSelectedPosition()))
        old_position=control.getSelectedPosition()
        old_key=catalog.media_key(self.media[old_position]) if 0<=old_position<len(self.media) else None
        self.media=media
        control.reset()
        control.addItems([item(m) for m in media])
        if old_key:
            control.selectItem(next((i for i,m in enumerate(media) if catalog.media_key(m)==old_key),0))
        self.getControl(4).setLabel('First found within your configured providers · '+str(len(media))+' titles' if media else 'No verified titles in this view yet. Connect accounts and choose providers to begin.')

    def refresh(self):
        if self.running:
            notice('Refresh already running')
            return
        if time.time()-read('last_refresh',0)<15:
            notice('Please wait briefly before refreshing again')
            return
        self.running=True
        def work():
            try:
                errors=catalog.refresh(preferences(),lambda:self.closed or MONITOR.abortRequested(),self.status)
                self.status('Checked '+time.strftime('%H:%M')+(' · Partial refresh: open Refresh details' if errors else ' · Up to date within configured coverage'))
                if not self.closed and self.tab==10:
                    self.render(catalog.available(preferences(),today=True))
            except Exception:
                self.status('Refresh failed. Check Accounts and Providers.')
            finally:
                self.running=False
        threading.Thread(target=work,daemon=True).start()

    def onClick(self,id_):
        try:
            if id_==100:
                i=self.getControl(100).getSelectedPosition()
                if 0<=i<len(self.media):
                    selected=self.media[i]
                    if selected['type'] in ('tv','season'):
                        self.render(catalog.seasons(selected) if selected['type']=='tv' else catalog.episodes(selected),remember=True)
                    elif selected['type']=='collection':
                        self.render(selected['members'],remember=True)
                    else:
                        play_sources(selected)
            elif id_ in (10,11,12,13,14,15):
                self.tab=id_
                self.history=[]
                if id_==10:
                    self.render(catalog.available(preferences(),today=True))
                elif id_==11:
                    self.render(catalog.discovery('movie',setting('discovery','trending')))
                elif id_==12:
                    self.render(catalog.discovery('tv',setting('discovery','trending')))
                elif id_==13:
                    self.render(catalog.available(preferences('episode'),kind='episode'))
                elif id_==14:
                    definitions=read('selected_lists',[])
                    self.render([{'id':str(d['id']),'type':'collection','title':d['name'],'members':catalog.list_items(d),
                                  'plot':'Selected list collection. Availability is checked separately per title.','poster':'','fanart':''} for d in definitions])
                else:
                    menu=['Local watchlist','Recently watched on Trakt']+[d['service'].upper()+' · '+d['name'] for d in read('selected_lists',[])]
                    j=DIALOG.select('My libraries',menu)
                    if j==0:
                        self.render(read('watchlist',[]))
                    elif j==1:
                        self.render(catalog.recent_history())
                    elif j>=2:
                        self.render(catalog.list_items(read('selected_lists',[])[j-2]))
            elif id_==20:
                connect()
            elif id_==21:
                provider_setup()
            elif id_==22:
                ADDON.openSettings()
            elif id_==23:
                self.refresh()
            elif id_==24:
                DIALOG.textviewer('Refresh details','\n'.join(read('refresh_errors',[])) or 'No errors recorded. Coverage is limited to the configured candidate pool.')
            elif id_==25:
                self.closed=True
                self.close()
        except Exception as e:
            DIALOG.ok('Lumen',str(e) if isinstance(e,(ApiError,RuntimeError)) else 'This action could not finish. Check setup or try again.')

    def onAction(self,action):
        id_=action.getId()
        if id_ in (9,10,92):
            if self.history:
                media,position=self.history.pop()
                self.render(media)
                self.getControl(100).selectItem(max(0,position))
                self.setFocusId(100 if self.media else 20)
            else:
                self.closed=True
                self.close()
        elif id_==117 and self.getFocusId()==100:
            i=self.getControl(100).getSelectedPosition()
            if 0<=i<len(self.media):
                try:
                    context(self.media[i])
                except Exception:
                    notice('Context action could not finish')

def device_preset():
    names=list(framework.DEVICES)
    selected=DIALOG.select('Device starting preferences',[framework.DEVICES[name]['name'] for name in names])
    if selected>=0 and DIALOG.yesno('Apply device preset','Replace quality and size preferences on this device? These are editable starting values, not hardware detection.'):
        framework.apply_device(names[selected])
        notice('Device preferences saved')

def clear_caches():
    if DIALOG.yesno('Clear cached discovery and searches','Clear cached searches and discovery? Accounts, resume positions, watchlists, providers and first-found history will be preserved.'):
        framework.clear_cache()
        notice('Discovery and search caches cleared')

def account_route(params):
    choices={'tmdb':0,'trakt':1,'mdb':2,'rd':3,'tb':4,'pm':5,'ad':6,'lists':7,'disconnect':8}
    if params.get('service') not in choices:
        raise ValueError('Unknown service')
    connect(choices[params['service']])

def show_home(force=False):
    if not force and setting('home.mode','dashboard')=='recovery':
        return
    window=Home('script-lumen-home.xml',ADDON.getAddonInfo('path'),'Default','720p')
    window.startup_error=None
    try:
        window.doModal()
    finally:
        window.closed=True
    if window.startup_error:
        DIALOG.textviewer('Lumen dashboard failed',window.startup_error+'\n\nUse the recovery menu below to access Accounts, Settings and Status.')
    del window

def run(argv):
    action,params=router.parse(argv)
    handlers={
        'home':lambda p:show_home(force=p.get('force')=='true'),
        'accounts':lambda p:connect(),
        'providers':lambda p:provider_setup(),
        'settings':lambda p:ADDON.openSettings(),
        'account':account_route,
        'device':lambda p:device_preset(),
        'status':lambda p:DIALOG.textviewer('Lumen status',framework.status()),
        'clear_cache':lambda p:clear_caches(),
        'trakt_setup':lambda p:connect(9),
    }
    try:
        router.dispatch(action,params,handlers)
    except Exception as error:
        report=failure_report(error,'route '+action)
        xbmc.log(report,xbmc.LOGERROR)
        DIALOG.textviewer('Lumen action failed',report+'\n\nReturn to Settings or Accounts to review setup.')
    if len(argv)>1 and str(argv[1]).lstrip('-').isdigit() and int(argv[1])>=0:
        handle=int(argv[1])
        for label,action,values in [('Open Lumen dashboard','home',{'force':'true'}),('Accounts','accounts',{}),
                                   ('Providers','providers',{}),('Settings','settings',{}),
                                   ('Device preferences','device',{}),('Status','status',{}),('Clear caches','clear_cache',{})]:
            xbmcplugin.addDirectoryItem(handle,url(action,**values),xbmcgui.ListItem(label),True)
        xbmcplugin.endOfDirectory(handle,succeeded=True,cacheToDisc=False)
