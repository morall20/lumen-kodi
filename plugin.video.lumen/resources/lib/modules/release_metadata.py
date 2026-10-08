"""Daily TMDB cache, external IDs and conservative title matching."""
import json
import time
from accounts import tmdb
from catalog import canonical
from runtime import setting
from . import release_database as database
from .release_parser import normalized


def key(parsed, ids):
    return json.dumps([setting('language','en-US'),parsed['media_type'],normalized(parsed['title']),
                       parsed['year'],parsed['season'],parsed['episode'],ids],sort_keys=True)


def cached(parsed, ids):
    updated,media=database.metadata(key(parsed,ids))
    return updated,media


def resolve(parsed, ids=None, stop=lambda:False, selected_id=None):
    ids=ids or {}
    cache_key=key(parsed,ids)
    updated,old=database.metadata(cache_key)
    if selected_id is None and updated>time.time()-86400:
        return old
    kind='tv' if parsed['media_type']=='episode' else 'movie'
    if stop():
        raise InterruptedError()
    id_=selected_id or ids.get('tmdb') or (old.get('show_id',old['id']) if old else None)
    if not id_ and (ids.get('imdb') or ids.get('tvdb')):
        external='imdb' if ids.get('imdb') else 'tvdb'
        found=tmdb('find/'+str(ids[external]),{'external_source':external+'_id'})
        results=found.get('tv_results' if kind=='tv' else 'movie_results',[])
        if len(results)==1:
            id_=results[0]['id']
    if not id_:
        params={'query':parsed['title'],'include_adult':'false'}
        if kind=='movie' and parsed['year']:
            params['year']=parsed['year']
        matches=[]
        for row in tmdb('search/'+kind,params).get('results',[])[:20]:
            names=[row.get(x,'') for x in ('title','name','original_title','original_name')]
            if normalized(parsed['title']) not in [normalized(n) for n in names]:
                continue
            if kind=='movie' and (not parsed['year'] or row.get('release_date','')[:4]!=parsed['year']):
                continue
            matches.append(row)
        if len(matches)==1:
            id_=matches[0]['id']
    if not id_:
        database.save_metadata(cache_key,None)
        return None
    if stop():
        raise InterruptedError()
    detail=tmdb('%s/%s'%(kind,id_),{'append_to_response':'external_ids,credits,videos,'+('release_dates' if kind=='movie' else 'content_ratings')})
    media=canonical(detail,kind)
    media.update(imdb=detail.get('imdb_id') or detail.get('external_ids',{}).get('imdb_id',''),
                 tvdb=detail.get('external_ids',{}).get('tvdb_id'),runtime=detail.get('runtime'),
                 genres=[g['name'] for g in detail.get('genres',[])],
                 cast=[p['name'] for p in detail.get('credits',{}).get('cast',[])[:15]],
                 trailers=[v for v in detail.get('videos',{}).get('results',[]) if v.get('site')=='YouTube' and v.get('type') in ('Trailer','Teaser')],
                 certifications=detail.get('release_dates',detail.get('content_ratings',{})).get('results',[]))
    if kind=='tv':
        if stop():
            raise InterruptedError()
        episode=tmdb('tv/%s/season/%s/episode/%s'%(id_,parsed['season'],parsed['episode']))
        media.update(type='episode',show_id=id_,show_title=media['title'],id=episode['id'],
                     title=episode['name'],season=parsed['season'],episode=parsed['episode'],
                     plot=episode.get('overview',''),date=episode.get('air_date',''),runtime=episode.get('runtime'),
                     fanart='https://image.tmdb.org/t/p/w780'+episode['still_path'] if episode.get('still_path') else media['fanart'])
    database.save_metadata(cache_key,media)
    return media
