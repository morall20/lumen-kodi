import time
from accounts import tmdb, trakt, mdb, active_services, verify
from runtime import read, write, setting, flag, preferences
from core import eligible, rank
from providers import search

def canonical(item, kind):
    title = item.get('title') or item.get('name') or ''
    date = item.get('release_date') or item.get('first_air_date') or ''
    return {'id':item['id'], 'type':kind, 'title':title, 'year':date[:4],
            'plot':item.get('overview',''), 'poster': 'https://image.tmdb.org/t/p/w342'+item['poster_path'] if item.get('poster_path') else '',
            'fanart':'https://image.tmdb.org/t/p/w780'+item['backdrop_path'] if item.get('backdrop_path') else '',
            'date':date, 'imdb':item.get('imdb_id',''), 'collection':item.get('belongs_to_collection')}

def detail(media):
    if media['type'] == 'collection' or (media.get('imdb') and media.get('year') and media.get('plot')):
        return media
    kind = 'tv' if media['type'] in ('tv','episode') else 'movie'
    id_ = media.get('show_id',media['id'])
    d = tmdb('%s/%s' % (kind,id_), {'append_to_response':'external_ids'})
    enriched=dict(media, imdb=media.get('imdb') or d.get('imdb_id') or d.get('external_ids',{}).get('imdb_id',''),
                  tvdb=d.get('external_ids',{}).get('tvdb_id',''), collection=d.get('belongs_to_collection'))
    enriched['year']=media.get('year') or (d.get('release_date') or d.get('first_air_date') or '')[:4]
    enriched['plot']=media.get('plot') or d.get('overview','')
    enriched['poster']=media.get('poster') or ('https://image.tmdb.org/t/p/w342'+d['poster_path'] if d.get('poster_path') else '')
    enriched['fanart']=media.get('fanart') or ('https://image.tmdb.org/t/p/w780'+d['backdrop_path'] if d.get('backdrop_path') else '')
    return enriched

def discovery(kind='movie', feed='trending'):
    key = 'catalog:%s:%s' % (kind,feed)
    if feed == 'trending':
        path, params = 'trending/%s/day'%kind, {}
    elif feed == 'latest':
        path, params = 'discover/'+kind, {'sort_by':'primary_release_date.desc' if kind=='movie' else 'first_air_date.desc',
            'primary_release_date.lte' if kind=='movie' else 'first_air_date.lte':time.strftime('%Y-%m-%d')}
    else:
        path, params = kind+'/popular', {}
    data = [canonical(x,kind) for x in tmdb(path,params).get('results', [])[:20]]
    write(key, data)
    return data

def seasons(media):
    d = tmdb('tv/%s'%media['id'])
    return [dict(media, type='season', season=x['season_number'], title='%s — %s'%(media['title'], x['name']),
                 show_title=media['title'], show_id=media['id']) for x in d.get('seasons',[]) if x['season_number']>0]

def episodes(media):
    show_id = media.get('show_id',media['id'])
    d = tmdb('tv/%s/season/%s'%(show_id,media['season']))
    result = []
    for x in d.get('episodes',[]):
        if x.get('air_date') and x['air_date'] <= time.strftime('%Y-%m-%d'):
            result.append(dict(media, id=x['id'], type='episode', title=x['name'],
                episode=x['episode_number'], plot=x.get('overview',''), date=x['air_date'],
                fanart='https://image.tmdb.org/t/p/w780'+x['still_path'] if x.get('still_path') else media.get('fanart','')))
    return result

def list_definitions(service):
    data = mdb('lists/user') if service == 'mdb' else trakt('users/me/lists')
    if isinstance(data,dict):
        data = data.get('lists',data.get('data',[]))
    return [{'service':service, 'id':x.get('id') or x.get('ids',{}).get('trakt'), 'name':x.get('name','List')}
            for x in data if x.get('id') or x.get('ids',{}).get('trakt')]

def list_items(definition):
    service, id_ = definition['service'], str(definition['id'])
    if service == 'mdb':
        d = mdb('lists/%s/items'%id_, {'limit':50})
        data = []
        if isinstance(d,dict):
            for key, kind in [('movies','movie'),('shows','tv')]:
                data.extend(dict(x, _kind=kind) for x in d.get(key, []))
        elif isinstance(d,list):
            data = d
    else:
        data = trakt('users/me/lists/%s/items'%id_, params={'limit':50})
    result = []
    for x in data[:50]:
        kind = x.get('type',x.get('mediatype',x.get('_kind','movie')))
        if kind in ('show','tv'):
            kind = 'tv'
        raw = x.get('movie') or x.get('show') or x
        id_ = raw.get('ids',{}).get('tmdb')
        if service=='mdb':
            id_ = id_ or raw.get('tmdb_id') or raw.get('id')
        if id_ and kind in ('movie','tv'):
            result.append({'id':id_, 'type':kind, 'title':raw.get('title',raw.get('name','')),
                           'year':raw.get('year',''), 'imdb':raw.get('ids',{}).get('imdb') or raw.get('imdb_id',''),
                           'plot':'', 'poster':'', 'fanart':'', 'list_added':x.get('listed_at') or x.get('added_at')})
    write('list:%s:%s'%(definition['service'],definition['id']), result)
    return result

def recent_history():
    result = []
    for x in trakt('users/me/history', params={'limit':30}):
        if x.get('movie'):
            raw = x['movie']
            if raw.get('ids',{}).get('tmdb'):
                result.append({'id':raw['ids']['tmdb'], 'type':'movie', 'title':raw['title'], 'year':raw.get('year',''),
                               'imdb':raw['ids'].get('imdb',''), 'watched_at':x.get('watched_at'), 'plot':'','poster':'','fanart':''})
        elif x.get('episode',{}).get('ids',{}).get('tmdb') and x.get('show',{}).get('ids',{}).get('tmdb'):
            raw, show = x['episode'], x['show']
            result.append({'id':raw['ids'].get('tmdb') or raw['ids'].get('trakt'), 'type':'episode', 'title':raw['title'],
                           'show_id':show['ids']['tmdb'], 'show_title':show['title'], 'year':show.get('year',''),
                           'imdb':show['ids'].get('imdb',''), 'season':raw['season'], 'episode':raw['number'],
                           'watched_at':x.get('watched_at'), 'plot':'','poster':'','fanart':''})
    return result

def media_key(media):
    return '%s:%s:%s:%s'%(media['type'],media.get('show_id',media['id']),media.get('season',''),media.get('episode',''))

def sources(media, prefs, fresh=False, cancel=lambda:False, services=None, selected_modules=None):
    media = detail(media)
    key = 'search:'+media_key(media)
    cached = read(key,{})
    if not fresh and cached.get('time',0)>time.time()-600:
        candidates = cached.get('sources',[])
        errors = []
    else:
        candidates, errors = search(media, cancel, selected_modules)
        write(key, {'time':time.time(), 'sources':candidates})
    results, err = verify(candidates, services if services is not None else active_services())
    errors += err
    remember(media, results)
    return sorted([x for x in results if eligible(x,prefs)], key=rank), errors

def remember(media, results):
    index = read('availability',{})
    first_scan = not read('baseline_complete',False)
    now = time.time()
    for source in results:
        key = media_key(media)+'|'+source['service']+'|'+(source.get('hash') or source['url'])
        old = index.get(key,{})
        if source['availability']=='ready':
            index[key] = {'media':media, 'source':source, 'first':old.get('first',now), 'checked':now,
                          'baseline':old.get('baseline', first_scan)}
        elif key in index:
            index[key]['source']['availability']='unknown'
    # Bound the observation index. First-found history is retained for this window only.
    index = dict(sorted(index.items(),key=lambda x:x[1]['checked'],reverse=True)[:2000])
    write('availability',index)

def available(prefs, today=False, kind=None):
    records = sorted(read('availability',{}).values(),key=lambda x:x['first'],reverse=True)
    result, seen = [], set()
    for record in records:
        source, media = record['source'],record['media']
        if source['availability']!='ready' or record['checked']<time.time()-3600 or not eligible(source, preferences('episode') if media['type']=='episode' else prefs):
            continue
        if today and time.strftime('%Y-%m-%d',time.localtime(record['first'])) != time.strftime('%Y-%m-%d'):
            continue
        if kind and media['type']!=kind:
            continue
        key=media_key(media)
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(media,badge=('First Found' if record['baseline'] else 'Newly Available')+' · '+source['resolution'],
                           available_at=record['first']))
    return result

def refresh(prefs, cancel=lambda:False, status=lambda x:None):
    selected = read('selected_lists',[]) if flag('list_widgets') else []
    pool, errors = [], []
    for definition in selected:
        try:
            pool.extend(list_items(definition))
        except Exception:
            errors.append(definition['name']+': list could not be refreshed')
    if not pool or not flag('lists_only'):
        try:
            pool.extend(discovery('movie','trending'))
            shows = discovery('tv','trending')
            write('home_shows',shows)
            for show in shows[:2]:
                d = tmdb('tv/%s'%show['id'])
                ep = d.get('last_episode_to_air')
                if ep:
                    pool.append(dict(show,type='episode',show_id=show['id'],show_title=show['title'],
                                     id=ep['id'],title=ep['name'],season=ep['season_number'],episode=ep['episode_number']))
        except Exception:
            errors.append('Catalog could not be refreshed; check TMDB setup')
    unique = {}
    for item in pool:
        if item['type'] in ('movie','episode'):
            unique[media_key(item)] = item
    limit = int(setting('refresh_limit','6'))
    ordered=list(unique.values())
    ordered=[x for x in ordered if x['type']=='episode'][:2]+[x for x in ordered if x['type']=='movie']+[x for x in ordered if x['type']=='episode'][2:]
    for i, item in enumerate(ordered[:limit]):
        if cancel():
            break
        status('Checking %s/%s · %s'%(i+1,min(limit,len(unique)),item['title']))
        try:
            _, err = sources(item,preferences(item['type']),fresh=True,cancel=cancel)
            errors.extend(err)
        except Exception:
            errors.append(item['title']+': search could not finish')
    if not cancel():
        write('baseline_complete',True)
    write('last_refresh',time.time())
    write('refresh_errors',list(dict.fromkeys(errors))[:20])
    return errors
