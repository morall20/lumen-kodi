"""Offline behavioral checks. API fixtures do not establish live compatibility."""
import copy
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'resources/lib'))
TEMP=tempfile.TemporaryDirectory()
class Addon:
    settings={}
    def __init__(self,*args): pass
    def getSetting(self,key): return self.settings.get(key,'')
    def getAddonInfo(self,key):
        return {'profile':TEMP.name,'path':str(ROOT),'version':'1.0.0','name':'Fixture','icon':''}.get(key,'')
    def setSetting(self,key,value): self.settings[key]=value
sys.modules['xbmcaddon']=types.SimpleNamespace(Addon=Addon)
sys.modules['xbmcvfs']=types.SimpleNamespace(translatePath=lambda x:x)
import core
import runtime
import accounts
import catalog

class Checks(unittest.TestCase):
    def setUp(self):
        Addon.settings={}
        with runtime.db() as c: c.execute('DELETE FROM state')
        for key in list(runtime.credentials()): runtime.credential(key,remove=True)

    def test_quality_and_source_are_separate(self):
        for name,res,kind in [('Film.2160p.WEB-DL','4K','WEB-DL'),('Film.1440p.WEBRip','2K','WEBRip'),('Film.1080p.DVDRip','1080p','DVDRip'),('Film.720p.DVDSCR','720p','Screener')]:
            a=core.attributes(name);self.assertEqual((a['resolution'],a['source_type']),(res,kind))
        self.assertEqual(core.attributes('Film.DVDRip')['resolution'],'Unknown')

    def test_profile_and_camera_filters(self):
        s=core.normalize({'name':'Film.2160p.WEBRip','hash':'a'*40,'size':20},'A')
        prefs=runtime.preferences();self.assertTrue(core.eligible(s,prefs))
        prefs['resolutions']=['720p'];self.assertFalse(core.eligible(s,prefs))
        prefs['resolutions']=['4K'];prefs['max_gb']=10;self.assertFalse(core.eligible(s,prefs))
        cam=dict(s,source_type='CAM');prefs['max_gb']=30;self.assertFalse(core.eligible(cam,prefs))
        Addon.settings={'episode.max_gb':'3','movie.max_gb':'20'}
        self.assertEqual(runtime.preferences('episode')['max_gb'],3)
        self.assertEqual(runtime.preferences('movie')['max_gb'],20)

    def test_exact_episode_file_matching(self):
        files=[{'path':'Show.S01E02.mkv'},{'path':'Show.S01E20.mkv'},{'path':'Show.S01E02.txt'}]
        self.assertEqual(core.video_files(files,{'type':'episode','season':1,'episode':2}),[files[0]])

    def test_dedup_preserves_url_case_and_provenance(self):
        s=core.normalize({'name':'Film','hash':'A'*40},'A')
        t=dict(s,modules=['B']);self.assertEqual(core.merge([s,t])[0]['modules'],['A','B'])
        a=core.normalize({'url':'https://example.com/Film.mp4'},'A')
        b=core.normalize({'url':'https://example.com/film.mp4'},'B')
        self.assertEqual(len(core.merge([a,b])),2)
        self.assertIsNone(core.normalize({'url':'javascript:bad'},'A'))

    def test_unknown_availability_not_false_ready(self):
        candidate=core.normalize({'hash':'a'*40,'name':'Film.1080p.WEBRip'},'A')
        with patch.object(accounts,'service_call',return_value=[]):
            rows,err=accounts.verify([candidate],['rd'])
        self.assertEqual(rows[0]['availability'],'unknown')
        with patch.object(accounts,'service_call',return_value={'a'*40:{'hash':'a'*40}}):
            rows,err=accounts.verify([candidate],['tb'])
        self.assertEqual(rows[0]['availability'],'ready')
        prefs=runtime.preferences();prefs['ready_only']=True
        self.assertFalse(core.eligible(candidate,prefs))

    def test_first_found_not_reset_on_return(self):
        media={'id':1,'type':'movie','title':'Fixture'}
        source=dict(core.normalize({'hash':'a'*40,'name':'Film.1080p.WEBRip'},'A'),service='tb',availability='ready',checked=100)
        with patch('catalog.time.time',return_value=100): catalog.remember(media,[source])
        first=next(iter(runtime.read('availability').values()))
        self.assertTrue(first['baseline']);self.assertEqual(first['first'],100)
        runtime.write('baseline_complete',True)
        with patch('catalog.time.time',return_value=200): catalog.remember(media,[dict(source,availability='unknown')])
        with patch('catalog.time.time',return_value=300): catalog.remember(media,[source])
        row=next(iter(runtime.read('availability').values()))
        self.assertEqual(row['first'],100);self.assertEqual(row['checked'],300)

    def test_api_failure_returns_unknown_and_error(self):
        candidate=core.normalize({'hash':'a'*40,'name':'Film.1080p.WEBRip'},'A')
        with patch.object(accounts,'service_call',side_effect=runtime.ApiError(429)):
            rows,err=accounts.verify([candidate],['tb'])
        self.assertEqual(rows[0]['availability'],'unknown');self.assertTrue(err)

    def test_selected_source_only_mutation(self):
        calls=[]
        def call(s,path,method='GET',params=None,data=None):
            calls.append(path)
            if path=='torrents': return []
            raise AssertionError('No mutation after rejected confirmation')
        source=core.normalize({'hash':'a'*40,'name':'Film.1080p.WEBRip','url':'magnet:?xt=urn:btih:'+'a'*40},'A')
        with patch.object(accounts,'service_call',side_effect=call):
            self.assertEqual(accounts.resolve('rd',source,{'type':'movie'},lambda x:None,lambda x:False,lambda x:False),'')
        self.assertEqual(calls,['torrents'])

    def test_credentials_not_in_database(self):
        runtime.credential('rd',{'token':'fixture-secret'})
        self.assertEqual(runtime.credential('rd')['token'],'fixture-secret')
        with runtime.db() as c:
            self.assertFalse(c.execute("SELECT value FROM state WHERE value LIKE '%fixture-secret%'").fetchall())
        runtime.credential('rd',remove=True);self.assertEqual(runtime.credential('rd'),{})

    def test_https_and_redirect_policy(self):
        with self.assertRaises(runtime.ApiError): runtime.request('http://example.com')
        with self.assertRaises(runtime.ApiError): runtime.NoRedirect().redirect_request(None,None,302,'',{},'https://example.com')

    def test_list_identity_not_list_arrival(self):
        raw={'movies':[{'id':4,'title':'Fixture','year':2000,'imdb_id':'tt1234567'}]}
        with patch.object(catalog,'mdb',return_value=raw):
            rows=catalog.list_items({'id':1,'service':'mdb'})
        self.assertEqual(rows[0]['id'],4)
        self.assertIsNone(rows[0]['list_added'])
        self.assertNotIn('available_at',rows[0])

    def test_manifest_settings_and_navigation(self):
        addon=ET.parse(ROOT/'addon.xml').getroot()
        self.assertEqual(addon.attrib['id'],'plugin.video.lumen')
        settings=ET.parse(ROOT/'resources/settings.xml').getroot()
        ids=[x.attrib['id'] for x in settings.findall('.//setting')]
        self.assertEqual(len(ids),len(set(ids)))
        for id_ in ['movie.4k','movie.2k','movie.1080','movie.720','episode.2k']:
            self.assertIn(id_,ids)
        window=ET.parse(ROOT/'resources/skins/Default/720p/script-lumen-home.xml').getroot()
        controls={x.attrib['id'] for x in window.findall('./controls/control')}
        for tag in ('onleft','onright','onup','ondown'):
            for x in window.findall('.//'+tag): self.assertIn(x.text,controls)

class StartupRegressionTests(unittest.TestCase):
    def test_settings_labels_have_bundled_localization(self):
        settings=ET.parse(ROOT/'resources/settings.xml').getroot()
        po=(ROOT/'resources/language/resource.language.en_gb/strings.po').read_text()
        for node in settings.iter():
            label=node.get('label')
            if label:
                self.assertTrue(label.isdigit(), 'Kodi labels must reference localized strings')
                self.assertIn('msgctxt "#'+label+'"',po)
        for control in settings.findall('.//control'):
            if control.get('type') in ('edit','list'):
                self.assertTrue(control.findtext('heading').isdigit())

    def load_app(self):
        from unittest.mock import MagicMock
        class SkinWindow:
            instances=[]
            def __init__(self,filename,path,*args):
                self.filename=filename
                self.controls={}
                self.was_closed=False
                self.instances.append(self)
                # Model Kodi's active-skin-first resolution: Home.xml is the
                # skin's window, which does not have Lumen's control IDs.
                if filename=='Home.xml':
                    ids=['1']
                else:
                    ids=[x.get('id') for x in ET.parse(Path(path)/'resources/skins/Default/720p'/filename).findall('./controls/control')]
                for id_ in ids:
                    control=MagicMock()
                    control.getSelectedPosition.return_value=-1
                    self.controls[int(id_)]=control
            def getControl(self,id_):return self.controls[id_]
            def setFocusId(self,id_):self.focus=id_
            def close(self):self.was_closed=True
            def doModal(self):self.onInit()
        dialog=MagicMock()
        modules={'xbmc':types.SimpleNamespace(Monitor=MagicMock(),LOGERROR=4,log=MagicMock()),
                 'xbmcgui':types.SimpleNamespace(WindowXMLDialog=SkinWindow,Dialog=lambda:dialog),
                 'xbmcplugin':MagicMock()}
        context=patch.dict(sys.modules,modules)
        context.start();self.addCleanup(context.stop)
        spec=importlib.util.spec_from_file_location('lumen_app_fixture',ROOT/'resources/lib/app.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module,SkinWindow,dialog

    def test_cold_start_uses_addon_window_with_empty_library(self):
        app,windows,dialog=self.load_app()
        with patch.object(app,'flag',return_value=False),patch.object(app.catalog,'available',return_value=[]):
            app.run(['plugin://plugin.video.lumen/','-1',''])
        window=windows.instances[-1]
        self.assertEqual(window.filename,'script-lumen-home.xml')
        self.assertIsNone(window.startup_error)
        self.assertEqual(window.focus,20)
        window.controls[4].setLabel.assert_called_once()
        dialog.textviewer.assert_not_called()

    def test_initialization_failure_closes_and_reports(self):
        app,windows,dialog=self.load_app()
        with patch.object(app.catalog,'available',side_effect=ValueError('secret-token-must-not-be-reported')):
            app.run(['plugin://plugin.video.lumen/','-1',''])
        self.assertTrue(windows.instances[-1].was_closed)
        report=dialog.textviewer.call_args.args[1]
        self.assertIn('ValueError',report)
        self.assertNotIn('secret-token',report)

if __name__=='__main__': unittest.main(verbosity=2)
