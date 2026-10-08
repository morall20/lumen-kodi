"""Background discovery only: never send feed URLs/hashes to debrid services."""
import hashlib
import threading
import time
from runtime import read, write, setting, flag, credential
from catalog import media_key
from . import release_database as database, release_metadata as metadata
from .release_parser import parse
from sources.releases import rss, api
from sources.releases.transport import fetch, validate_url


def sources():
    return read('radar.sources',[])[:4]


def add_source(config):
    config=dict(config)
    config['url']=validate_url(config['url'])
    if config.get('kind') not in ('rss','api') or not str(config.get('name','')).strip():
        raise ValueError('Choose RSS/Atom or JSON API and a source name')
    current=sources()
    if len(current)>=4:
        raise ValueError('Maximum four sources; remove one first')
    config['name']=str(config['name']).strip()[:80]
    config['id']=hashlib.sha256(config['url'].encode()).hexdigest()[:24]
    config['enabled']=True
    if any(s['id']==config['id'] for s in current):
        raise ValueError('That endpoint is already registered')
    current.append(config)
    write('radar.sources',current)


def accepts(parsed, view='all'):
    if not flag('radar.'+('tv' if parsed['media_type']=='episode' else 'movies'),True):
        return False
    if view in ('movie','episode') and parsed['media_type']!=view:
        return False
    resolution={'2160p':2160,'1440p':1440,'1080p':1080,'720p':720,'480p':480}.get(parsed['resolution'],0)
    minimum=int(setting('radar.minimum','720'))
    if resolution<minimum:
        return False
    if parsed['hdr'] and not flag('radar.hdr',True):
        return False
    if parsed['dolby_vision'] and not flag('radar.dv',True):
        return False
    if view=='uhd' and resolution!=2160 and not parsed['hdr'] and not parsed['dolby_vision']:
        return False
    return True


def record_key(source_id, parsed):
    return hashlib.sha256((source_id+'|'+parsed['name'].casefold()).encode()).hexdigest()


def refresh(force=False, cancel=lambda:False):
    configured=[s for s in sources() if s.get('enabled')]
    if not flag('radar.enabled',True) or not configured:
        return {'state':'disabled' if not flag('radar.enabled',True) else 'no_sources'}
    token=database.acquire(max(5,int(setting('radar.interval','30')))*60,force)
    if not token:
        return {'state':'cached_or_busy'}
    deadline=time.monotonic()+60
    stop=lambda:cancel() or time.monotonic()>=deadline or not flag('radar.enabled',True)
    errors=[]
    count=0
    try:
        for source in configured:
            if stop():
                break
            try:
                validators=database.get('validators:'+source['id'],{})
                raw,tags=fetch(source['url'],validators)
                if raw is not None:
                    entries=(rss if source['kind']=='rss' else api).parse(raw,source)
                    for entry in entries:
                        parsed=parse(entry['title'])
                        if not parsed['title']:
                            continue
                        published=entry.get('published',0)
                        # Treat future or malformed publisher dates as undated announcements.
                        if published>time.time()+300 or published<0:
                            published=0
                        key=record_key(source['id'],parsed)
                        _,media=metadata.cached(parsed,entry.get('ids',{}))
                        database.save(key,{'key':key,'source_id':source['id'],'source_name':source['name'],
                                          'parsed':parsed,'published':published,'ids':entry.get('ids',{}),'media':media})
                        count+=1
                # Advance conditional validators only after successful parse/storage.
                database.put('validators:'+source['id'],tags)
            except Exception:
                errors.append({'source_id':source['id'],'stage':'feed'})
        enriched=0
        if credential('tmdb').get('token'):
            for record in database.records():
                if stop() or enriched>=8:
                    break
                if record['source_id'] not in [s['id'] for s in configured] or not accepts(record['parsed']):
                    continue
                updated,media=metadata.cached(record['parsed'],record.get('ids',{}))
                if updated>time.time()-86400:
                    if record.get('media')!=media:
                        database.save(record['key'],dict(record,media=media))
                    continue
                enriched+=1
                try:
                    media=metadata.resolve(record['parsed'],record.get('ids',{}),stop)
                    database.save(record['key'],dict(record,media=media))
                except InterruptedError:
                    break
                except Exception:
                    errors.append({'source_id':record['source_id'],'stage':'metadata'})
        result={'state':'partial' if errors or stop() else 'complete','time':time.time(),
                'announcements':count,'metadata_attempts':enriched,'errors':errors}
        database.put('status',result)
        return result
    finally:
        database.release(token)


def start(force=False, cancel=lambda:False, finished=lambda result:None):
    def work():
        try:
            result=refresh(force,cancel)
        except Exception:
            result={'state':'failed'}
        finished(result)
    thread=threading.Thread(target=work,name='LumenReleaseRadar',daemon=True)
    thread.start()
    return thread


def items(view='all'):
    if not flag('radar.enabled',True):
        return []
    enabled={s['id'] for s in sources() if s.get('enabled')}
    result=[]
    seen=set()
    preferred=setting('radar.preferred','2160p')
    records=database.records()
    # Preserve newest-title ordering; use preferred resolution to choose variants
    # announced at the same timestamp only, never move old titles ahead of new ones.
    records.sort(key=lambda r:(r['published'] or r['first_seen'],r['parsed']['resolution']==preferred,r['first_seen']),reverse=True)
    for record in records:
        parsed=record['parsed']
        if record['source_id'] not in enabled or not accepts(parsed,view):
            continue
        media=record.get('media')
        if media:
            media=dict(media)
            identity=media_key(media)
        else:
            identity=record['key']
            media={'id':identity,'type':'announcement','title':parsed['title'],'year':parsed['year'],
                   'plot':'Metadata match pending. Use Select to match this announcement before choosing playback sources.',
                   'poster':'','fanart':''}
        if identity in seen:
            continue
        seen.add(identity)
        label='Announced' if record['published'] else 'First seen'
        day=time.strftime('%b %d',time.localtime(record['published'] or record['first_seen']))
        media.update(badge='%s %s · %s · %s'%(label,day,parsed['resolution'] or 'SD/unknown',parsed['source']),
                     radar_key=record['key'],radar_parsed=parsed)
        result.append(media)
        if len(result)>=100:
            break
    return result


def status():
    result=database.get('status',{})
    names={s['id']:s['name'].replace('[','(').replace(']',')') for s in sources()}
    rows=['Release Radar: '+result.get('state','not refreshed'),
          'Sources enabled: '+str(sum(bool(s.get('enabled')) for s in sources())),
          'Cached announcements: '+str(len(database.records())),
          'TMDB metadata: '+('configured' if credential('tmdb').get('token') else 'connect TMDB in Accounts')]
    if result.get('time'):
        rows.append('Last attempt: '+time.strftime('%Y-%m-%d %H:%M',time.localtime(result['time'])))
    rows.extend(names.get(e['source_id'],'Source')+': '+e['stage']+' could not refresh' for e in result.get('errors',[]))
    rows.append('Announced/first-seen dates are discovery dates, not debrid upload dates. Playback is checked separately.')
    return '\n'.join(rows)
