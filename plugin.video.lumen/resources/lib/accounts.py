"""Service-specific API clients. No shared or inherited application keys."""
import time
from urllib.parse import quote
from runtime import request, credential, setting, ApiError
from core import video_files

SERVICES = {'rd': 'Real-Debrid', 'tb': 'TorBox', 'pm': 'Premiumize', 'ad': 'AllDebrid'}
BASES = {'rd': 'https://api.real-debrid.com/rest/1.0/', 'tb': 'https://api.torbox.app/v1/api/',
         'pm': 'https://www.premiumize.me/api/', 'ad': 'https://api.alldebrid.com/v4/'}

def active_services():
    return [s for s in SERVICES if credential(s).get('token') and setting(s+'.enabled', 'true') == 'true']

def service_call(service, path, method='GET', params=None, data=None):
    token = credential(service).get('token', '')
    if not token:
        raise ApiError(401)
    p = dict(params or {})
    if service == 'ad':
        p['agent'] = 'Lumen'
    d = request(BASES[service] + path, method, params=p, data=data,
                headers={'Authorization': 'Bearer ' + token}, form=True)
    if service == 'tb':
        if d.get('success') is not True:
            raise ApiError(400)
        return d.get('data')
    if service in ('pm', 'ad'):
        if d.get('status') != 'success':
            raise ApiError(400)
        return d.get('data', d)
    return d

def validate(service, token):
    path = {'rd':'user', 'tb':'user/me', 'pm':'account/info', 'ad':'user'}[service]
    params = {'agent':'Lumen'} if service == 'ad' else None
    d = request(BASES[service]+path, params=params, headers={'Authorization':'Bearer '+token})
    if service == 'tb' and d.get('success') is not True:
        raise ApiError(401)
    if service in ('ad', 'pm') and d.get('status') != 'success':
        raise ApiError(401)
    return d

def verify(sources, services):
    result, errors = [], []
    hashes = list(dict.fromkeys(x['hash'] for x in sources if x.get('hash')))[:100]
    for service in services:
        available = set()
        try:
            if service == 'tb' and hashes:
                d = service_call(service, 'torrents/checkcached', params={'hash':','.join(hashes), 'format':'object', 'list_files':'true'})
                if isinstance(d, dict):
                    available = {h.lower() for h, value in d.items() if value}
                elif isinstance(d, list):
                    available = {str(x.get('hash','')).lower() if isinstance(x,dict) else str(x).lower() for x in d}
            elif service == 'pm' and hashes:
                d = service_call(service, 'cache/check', 'POST', data={'items[]':hashes})
                available = {h for h, cached in zip(hashes, d.get('response', [])) if cached is True}
            elif service == 'rd':
                # Only account torrents are observable through the documented list endpoint.
                d = service_call(service, 'torrents', params={'limit':100})
                available = {str(x.get('hash','')).lower() for x in d if x.get('status') == 'downloaded'}
            elif service == 'ad':
                d = service_call(service, 'magnet/status')
                magnets = d.get('magnets', [])
                if isinstance(magnets, dict):
                    magnets = [magnets]
                available = {str(x.get('hash','')).lower() for x in magnets if x.get('statusCode') == 4}
            for source in sources:
                item = dict(source, service=service, checked=time.time())
                item['availability'] = 'ready' if source.get('hash') in available else 'unknown'
                result.append(item)
        except ApiError:
            errors.append(SERVICES[service] + ': availability could not be checked')
            result.extend(dict(s, service=service, availability='unknown', checked=0) for s in sources)
    return result, errors

def resolve(service, source, media, choose, confirm, wait):
    """Mutations occur only after selection. No cloud probing at startup."""
    hash_, url = source.get('hash'), source['url']
    if service == 'rd':
        if hash_:
            existing = service_call(service, 'torrents', params={'limit':100})
            torrent = next((t for t in existing if t.get('hash','').lower() == hash_), None)
            if not torrent:
                if not confirm('Add this selected torrent to Real-Debrid? It may need downloading. No other sources will be added.'):
                    return ''
                torrent = service_call(service, 'torrents/addMagnet', 'POST', data={'magnet':url})
            id_ = str(torrent['id'])
            for _ in range(15):
                torrent = service_call(service, 'torrents/info/'+quote(id_))
                if torrent.get('status') in ('waiting_files_selection','downloaded'):
                    break
                if torrent.get('status') in ('error','magnet_error','virus','dead') or wait(1):
                    raise ApiError(0)
            files = video_files(torrent.get('files', []), media)
            if not files:
                raise ApiError(0, 'no_matching_video')
            selected = choose(files)
            if not selected:
                return ''
            if torrent.get('status') == 'waiting_files_selection':
                service_call(service, 'torrents/selectFiles/'+quote(id_), 'POST', data={'files':str(selected['id'])})
                torrent = service_call(service, 'torrents/info/'+quote(id_))
            if torrent.get('status') != 'downloaded':
                raise ApiError(0, 'download_not_ready')
            chosen = [x for x in torrent.get('files', []) if x.get('selected')]
            index = next((i for i, x in enumerate(chosen) if x['id'] == selected['id']), None)
            if index is None or index >= len(torrent.get('links', [])):
                raise ApiError(0)
            url = torrent['links'][index]
        return service_call(service, 'unrestrict/link', 'POST', data={'link':url}).get('download','')
    if service == 'tb':
        if not hash_:
            raise ApiError(0, 'torrent_required')
        if not confirm('Add this selected cached source to your TorBox account?'):
            return ''
        made = service_call(service, 'torrents/createtorrent', 'POST', data={'magnet':url, 'add_only_if_cached':'true'})
        id_ = made['torrent_id']
        torrent = service_call(service, 'torrents/mylist', params={'id':id_, 'bypass_cache':'true'})
        if isinstance(torrent, list):
            torrent = torrent[0] if torrent else {}
        if not torrent.get('download_finished'):
            raise ApiError(0, 'download_not_ready')
        files = video_files(torrent.get('files', []), media)
        selected = choose(files)
        if not selected:
            return ''
        return service_call(service, 'torrents/requestdl', params={'token':credential(service)['token'], 'torrent_id':id_, 'file_id':selected['id'], 'redirect':'false'})
    if service == 'pm':
        d = service_call(service, 'transfer/directdl', 'POST', data={'src':url})
        files = video_files(d.get('content', []), media)
        selected = choose(files)
        return selected.get('link','') if selected else ''
    raise ApiError(0, 'playback_not_implemented')

def trakt(path, method='GET', data=None, params=None, auth=True):
    c = credential('trakt')
    client_id = credential('trakt_app').get('client_id','')
    if not client_id or (auth and not c.get('access_token')):
        raise ApiError(401)
    if auth and time.time() >= c.get('created_at',0)+c.get('expires_in',0)-60:
        app = credential('trakt_app')
        fresh = request('https://api.trakt.tv/oauth/token', 'POST', data={'refresh_token':c.get('refresh_token'),
                        'client_id':client_id, 'client_secret':app.get('client_secret'),
                        'redirect_uri':'urn:ietf:wg:oauth:2.0:oob', 'grant_type':'refresh_token'})
        credential('trakt', fresh)
        c = fresh
    headers = {'trakt-api-key':client_id, 'trakt-api-version':'2', 'Content-Type':'application/json'}
    if auth:
        headers['Authorization'] = 'Bearer '+c['access_token']
    return request('https://api.trakt.tv/'+path, method, data=data, params=params, headers=headers)

def mdb(path, params=None):
    token = credential('mdb').get('token')
    if not token:
        raise ApiError(401)
    return request('https://api.mdblist.com/'+path, params=dict(params or {}, apikey=token))

def tmdb(path, params=None):
    key = credential('tmdb').get('token')
    if not key:
        raise ApiError(401, 'tmdb_setup_required')
    # Accept a TMDB v3 API key or v4 API read-access bearer token.
    p = dict(params or {}, language=setting('language','en-US'))
    headers = {}
    if len(key) == 32:
        p['api_key'] = key
    else:
        headers['Authorization'] = 'Bearer '+key
    return request('https://api.themoviedb.org/3/'+path, params=p, headers=headers)
