"""Behavioral fixtures; no Kodi hardware, live feeds or service credentials."""
import json
import threading
import time
import unittest
from unittest.mock import patch
import test_lumen as fixtures
Addon, runtime = fixtures.Addon, fixtures.runtime
from modules import release_parser as parser, release_database as database
from modules import release_radar as radar, release_metadata as metadata
from sources.releases import rss, api
from sources.releases.transport import validate_url, fetch, MAX_BYTES


class RadarTests(unittest.TestCase):
    def setUp(self):
        fixtures.Checks.setUp(self)
        with database.connection() as c:
            for table in ('radar_release','radar_metadata','radar_control'):
                c.execute('DELETE FROM '+table)

    def source(self,name='Fixture',url='https://example.com/feed',kind='rss'):
        radar.add_source({'name':name,'url':url,'kind':kind})
        return radar.sources()[-1]

    def record(self,name='Example.Movie.2026.2160p.WEB-DL.DDP5.1.DV.HDR.HEVC-GROUP',published=100,media=None):
        source=radar.sources()[0] if radar.sources() else self.source()
        parsed=parser.parse(name);key=radar.record_key(source['id'],parsed)
        data={'key':key,'parsed':parsed,'published':published,'source_id':source['id'],'source_name':source['name'],'ids':{},'media':media}
        database.save(key,data,now=200)
        return data

    def test_requested_movie_fields(self):
        p=parser.parse('Example.Movie.2026.2160p.WEB-DL.DDP5.1.DV.HDR.HEVC-GROUP')
        expected={'title':'Example Movie','year':'2026','media_type':'movie','resolution':'2160p',
                  'source':'WEB-DL','audio':'DDP 5.1','dolby_vision':True,'hdr':True,'codec':'HEVC','releasegroup':'GROUP'}
        for key,value in expected.items():self.assertEqual(p[key],value,key)

    def test_episode_and_quality_variants(self):
        p=parser.parse('Example.Show.S03E07.1080p.WEB-DL.x264-GROUP.mkv')
        self.assertEqual((p['title'],p['media_type'],p['season'],p['episode'],p['codec']),('Example Show','episode',3,7,'AVC'))
        for q,res in [('4K','2160p'),('2K','1440p'),('1440p','1440p'),('720p','720p')]:
            self.assertEqual(parser.parse('Example.Movie.2026.'+q+'.BluRay')['resolution'],res)
        self.assertEqual(parser.parse('Example.Show.3x07.720p.WEBRip')['episode'],7)
        underscored=parser.parse('Example_Show_S03E07_1080p_WEB_DL_HDR_HEVC-GROUP')
        self.assertEqual((underscored['title'],underscored['episode'],underscored['source'],underscored['hdr']),('Example Show',7,'WEB-DL',True))
        for name,kind in [('DVDRip','DVDRip'),('DVDSCR','Screener'),('STREAM','Stream'),('WEBRip','WEBRip')]:
            self.assertEqual(parser.parse('Example.2026.1080p.'+name)['source'],kind)

    def test_rss_atom_dates_and_no_links(self):
        raw=b'<rss><channel><item><title>Example.2026.1080p.WEBRip</title><pubDate>Thu, 08 Oct 2026 12:00:00 GMT</pubDate><link>https://example.com/private?token=secret</link><enclosure url="magnet:?secret"/></item></channel></rss>'
        result=rss.parse(raw)
        self.assertGreater(result[0]['published'],0)
        self.assertNotIn('secret',json.dumps(result))
        atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Example.2026.720p</title><published>2026-10-08T12:00:00Z</published></entry></feed>'
        self.assertEqual(rss.parse(atom)[0]['published'],result[0]['published'])
        self.assertEqual(rss.timestamp('nonsense'),0)

    def test_xml_entity_rejection_and_item_limit(self):
        evil='<!DOCTYPE rss [<!ENTITY x "secret">]><rss><channel><item><title>&x;</title></item></channel></rss>'
        for encoding in ('utf-8','utf-16','utf-32'):
            with self.assertRaises(ValueError):rss.parse(evil.encode(encoding))
        raw=('<rss><channel>'+('<item><title>Example.2026.1080p</title></item>'*100)+'</channel></rss>').encode()
        self.assertEqual(len(rss.parse(raw)),50)

    def test_json_mapping_ids_and_discarded_urls(self):
        raw=json.dumps({'data':{'rows':[{'name':'Example.2026.1080p','date':'2026-10-08T12:00:00Z',
                                      'identifiers':{'tmdb':7,'imdb':'tt1234567'},'url':'magnet:?secret'}]}}).encode()
        result=api.parse(raw,{'items_field':'data.rows','title_field':'name','date_field':'date','tmdb_field':'identifiers.tmdb','imdb_field':'identifiers.imdb'})
        self.assertEqual(result[0]['ids'],{'tmdb':7,'imdb':'tt1234567'})
        self.assertNotIn('magnet',json.dumps(result))
        self.assertEqual(api.parse(b'[{"title":"Example"}]',{'items_field':''})[0]['title'],'Example')
        with self.assertRaises(ValueError):api.parse(b'{}',{})
        with self.assertRaises(ValueError):api.field({},'__import__(evil)')

    def test_public_https_only_and_source_limits(self):
        for url in ('http://example.com/feed','https://user:pass@example.com/feed','https://127.0.0.1/feed','https://localhost/feed','https://example.com:444/feed','file:///tmp/a'):
            with self.assertRaises(ValueError):validate_url(url)
        for i in range(4):self.source(str(i),'https://example.com/'+str(i))
        with self.assertRaises(ValueError):self.source('Fifth','https://example.com/5')
        self.assertEqual(len(radar.sources()),4)

    def test_transport_size_and_conditional_304(self):
        from unittest.mock import MagicMock
        from urllib.error import HTTPError
        opener=MagicMock();response=opener.open.return_value.__enter__.return_value
        response.read.return_value=b'a'*(MAX_BYTES+1)
        with patch('sources.releases.transport.build_opener',return_value=opener):
            with self.assertRaises(ValueError):fetch('https://example.com/feed')
            opener.open.side_effect=HTTPError('https://example.com/feed',304,'',{},None)
            self.assertEqual(fetch('https://example.com/feed',{'If-None-Match':'etag'}),(None,{'If-None-Match':'etag'}))

    def test_cross_connection_lease_ttl_and_manual_cooldown(self):
        token=database.acquire(1800,now=10000)
        self.assertIsNotNone(token)
        self.assertIsNone(database.acquire(1800,True,now=10070))
        database.release('wrong-token')
        self.assertIsNone(database.acquire(1800,True,now=10070))
        database.release(token)
        self.assertIsNone(database.acquire(1800,now=11000))
        next_=database.acquire(1800,True,now=10070)
        self.assertIsNotNone(next_)
        database.release(next_)
        self.assertIsNone(database.acquire(1800,True,now=10080))
        self.assertIsNotNone(database.acquire(1800,now=12000))

    def test_concurrent_callers_only_one_lease(self):
        barrier=threading.Barrier(2);results=[]
        def caller():
            barrier.wait();results.append(database.acquire(1800))
        threads=[threading.Thread(target=caller) for _ in range(2)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(sum(t is not None for t in results),1)

    def test_first_seen_retained_clear_preserves_accounts_and_sources(self):
        record=self.record(published=0)
        database.save(record['key'],record,now=300)
        self.assertEqual(database.records()[0]['first_seen'],200)
        runtime.credential('tmdb',{'token':'fixture-key'})
        token=database.acquire(1800)
        self.assertFalse(database.clear())
        database.release(token)
        self.assertTrue(database.clear())
        self.assertEqual(database.records(),[])
        self.assertEqual(len(radar.sources()),1)
        self.assertEqual(runtime.credential('tmdb')['token'],'fixture-key')

    def test_radar_filters_independent_of_playback_filters(self):
        p=parser.parse('Example.2026.2160p.HDR.DV.WEB-DL')
        self.assertTrue(radar.accepts(p,'uhd'))
        Addon.settings['movie.4k']='false'
        self.assertTrue(radar.accepts(p))
        Addon.settings['radar.dv']='false'
        self.assertFalse(radar.accepts(p))
        Addon.settings={'radar.minimum':'1440'}
        self.assertFalse(radar.accepts(parser.parse('Example.2026.1080p.WEBRip')))
        self.assertTrue(radar.accepts(parser.parse('Example.2026.1440p.WEBRip')))
        Addon.settings={'radar.tv':'false'}
        self.assertFalse(radar.accepts(parser.parse('Example.S01E01.1080p.WEBRip')))

    def test_disabled_or_fresh_cache_makes_no_network_calls(self):
        self.source();Addon.settings['radar.enabled']='false'
        with patch.object(radar,'fetch') as fetch_:
            self.assertEqual(radar.refresh()['state'],'disabled');fetch_.assert_not_called()
        Addon.settings={}
        database.put('attempt',time.time())
        with patch.object(radar,'fetch') as fetch_:
            self.assertEqual(radar.refresh()['state'],'cached_or_busy');fetch_.assert_not_called()

    def test_read_views_are_offline_and_never_report_ready(self):
        self.record()
        with patch.object(radar,'fetch',side_effect=AssertionError('network')),patch.object(metadata,'tmdb',side_effect=AssertionError('network')):
            rows=radar.items('uhd')
        self.assertEqual(rows[0]['type'],'announcement')
        self.assertIn('Announced',rows[0]['badge'])
        self.assertNotIn('ready',json.dumps(rows).lower())

    def test_partial_failure_retains_cache_and_does_not_commit_bad_etag(self):
        record=self.record()
        with patch.object(radar,'fetch',return_value=(b'bad xml',{'If-None-Match':'bad'})):
            result=radar.refresh()
        self.assertEqual(result['state'],'partial')
        self.assertEqual(len(database.records()),1)
        self.assertEqual(database.get('validators:'+record['source_id'],{}),{})
        self.assertNotIn('url',json.dumps(result))
        self.assertNotIn('lease',database.get('lease',{}))

    def test_feed_and_metadata_never_call_playback_providers(self):
        self.source()
        payload=b'<rss><channel><item><title>Example.Movie.2026.1080p.WEBRip</title><link>magnet:?secret</link></item></channel></rss>'
        with patch.object(radar,'fetch',return_value=(payload,{})),patch('catalog.sources',side_effect=AssertionError('playback called')),patch('accounts.verify',side_effect=AssertionError('debrid called')):
            result=radar.refresh()
        self.assertEqual(result['announcements'],1)
        self.assertNotIn('magnet',json.dumps(database.records()))

    def test_metadata_conservative_match_daily_cache_and_external_ids(self):
        p=parser.parse('Example.Movie.2026.1080p.WEBRip')
        detail={'id':7,'title':'Example Movie','release_date':'2026-01-01','imdb_id':'tt1234567','overview':'Plot','poster_path':'/a.jpg'}
        def call(path,params=None):
            if path=='search/movie':return {'results':[detail]}
            if path=='movie/7':return detail
            raise AssertionError(path)
        with patch.object(metadata,'tmdb',side_effect=call) as api_:
            media=metadata.resolve(p)
            self.assertEqual(media['id'],7)
            self.assertEqual(media['imdb'],'tt1234567')
            self.assertEqual(metadata.resolve(p),media)
            self.assertEqual(api_.call_count,2)
        database.clear()
        with patch.object(metadata,'tmdb',return_value={'results':[dict(detail,title='Wrong Movie')]}):
            self.assertIsNone(metadata.resolve(p))
        database.clear()
        with patch.object(metadata,'tmdb',return_value={'results':[detail,dict(detail,id=8)]}):
            self.assertIsNone(metadata.resolve(p))

    def test_episode_mapping_show_ids_and_negative_cache(self):
        p=parser.parse('Example.Show.S03E07.1080p.WEB-DL')
        def call(path,params=None):
            if path=='find/tt1234567':return {'tv_results':[{'id':9}]}
            if path=='tv/9':return {'id':9,'name':'Example Show','first_air_date':'2020-01-01','external_ids':{'imdb_id':'tt1234567','tvdb_id':44}}
            if path=='tv/9/season/3/episode/7':return {'id':99,'name':'Episode Seven','air_date':'2026-10-01'}
            raise AssertionError(path)
        with patch.object(metadata,'tmdb',side_effect=call):
            media=metadata.resolve(p,{'imdb':'tt1234567'})
        self.assertEqual((media['type'],media['id'],media['show_id'],media['season'],media['episode']),('episode',99,9,3,7))
        other=parser.parse('Unmatched.Movie.2026.720p')
        with patch.object(metadata,'tmdb',return_value={'results':[]}) as api_:
            self.assertIsNone(metadata.resolve(other));self.assertIsNone(metadata.resolve(other))
            self.assertEqual(api_.call_count,1)

    def test_manual_id_retained_when_daily_metadata_expires(self):
        p=parser.parse('Alternate.Movie.2026.720p')
        database.save_metadata(metadata.key(p,{}),{'id':77,'type':'movie'})
        with database.connection() as c:c.execute('UPDATE radar_metadata SET updated=0')
        with patch.object(metadata,'tmdb',return_value={'id':77,'title':'Canonical Movie','release_date':'2026-01-01'}) as api_:
            self.assertEqual(metadata.resolve(p)['id'],77)
            self.assertEqual(api_.call_args.args[0],'movie/77')

    def test_refresh_metadata_work_is_bounded(self):
        self.source();runtime.credential('tmdb',{'token':'fixture'})
        for i in range(20):self.record(name='Example.Movie%d.2026.1080p.WEBRip'%i,published=i)
        with patch.object(radar,'fetch',return_value=(None,{})),patch.object(metadata,'resolve',return_value=None) as resolve_:
            result=radar.refresh()
        self.assertEqual(result['metadata_attempts'],8)
        self.assertEqual(resolve_.call_count,8)

    def test_cancel_skips_network_and_releases_lease(self):
        self.source()
        with patch.object(radar,'fetch') as fetch_:
            result=radar.refresh(cancel=lambda:True)
            fetch_.assert_not_called()
        self.assertEqual(result['state'],'partial')
        self.assertEqual(database.get('lease',{}),{})


if __name__=='__main__':unittest.main()
