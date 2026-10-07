import json
import os
import sqlite3
import threading
import time
import xbmcaddon
import xbmcvfs
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

ADDON = xbmcaddon.Addon('plugin.video.lumen')
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
os.makedirs(PROFILE, exist_ok=True)
LOCK = threading.RLock()

def setting(key, default=''):
    return ADDON.getSetting(key) or default

def flag(key, default=False):
    return setting(key, str(default).lower()) == 'true'

class ApiError(Exception):
    def __init__(self, status=0, code='', retry=0):
        self.status, self.code, self.retry = status, str(code), retry
        super().__init__('API request failed (%s). Reconnect the account or retry later.' % status)

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward an API Authorization header to a different host.
        raise ApiError(code, 'redirect_blocked')

_cooldowns = {}
def request(url, method='GET', params=None, data=None, headers=None, form=False):
    if urlparse(url).scheme != 'https':
        raise ApiError(0, 'https_required')
    host = urlparse(url).netloc
    if _cooldowns.get(host, 0) > time.time():
        raise ApiError(429, 'cooldown', int(_cooldowns[host] - time.time()) + 1)
    if params:
        url += ('&' if '?' in url else '?') + urlencode(params, doseq=True)
    h = {'User-Agent': 'Lumen/'+ADDON.getAddonInfo('version'), 'Accept': 'application/json'}
    h.update(headers or {})
    body = None
    if data is not None:
        h['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
        body = (urlencode(data, doseq=True) if form else json.dumps(data)).encode('utf-8')
    try:
        with build_opener(NoRedirect()).open(Request(url, data=body, headers=h, method=method), timeout=12) as resp:
            raw = resp.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ApiError(0, 'response_too_large')
            return json.loads(raw) if raw else {}
    except HTTPError as err:
        retry = int(err.headers.get('Retry-After', '30')) if str(err.headers.get('Retry-After', '30')).isdigit() else 30
        if err.code == 429:
            _cooldowns[host] = time.time() + retry
        try:
            payload = json.loads(err.read(4096))
            code = payload.get('error', '')
        except (ValueError, AttributeError):
            code = ''
        raise ApiError(err.code, code, retry) from None
    except (URLError, TimeoutError, ValueError, OSError):
        raise ApiError(0, 'network_or_response') from None

def db():
    c = sqlite3.connect(os.path.join(PROFILE, 'lumen.db'), timeout=15)
    c.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    return c

def read(key, default=None):
    with LOCK, db() as c:
        row = c.execute('SELECT value FROM state WHERE key=?', (key,)).fetchone()
    return json.loads(row[0]) if row else default

def write(key, value):
    with LOCK, db() as c:
        c.execute('INSERT OR REPLACE INTO state VALUES (?,?)', (key, json.dumps(value)))

def clear_search():
    with LOCK, db() as c:
        c.execute("DELETE FROM state WHERE key LIKE 'search:%'")

def credentials():
    with LOCK:
        try:
            with open(os.path.join(PROFILE, 'accounts.json'), encoding='utf-8') as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

def credential(key, value=None, remove=False):
    with LOCK:
        all_ = credentials()
        if value is None and not remove:
            return all_.get(key, {})
        if remove:
            all_.pop(key, None)
        else:
            all_[key] = value
        path = os.path.join(PROFILE, 'accounts.json')
        tmp = path + '.tmp'
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(all_, f)
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

def preferences(media_type='movie'):
    prefix = 'episode' if media_type == 'episode' else 'movie'
    return {'resolutions': [r for r, k in [('4K','4k'),('2K','2k'),('1080p','1080'),('720p','720')] if flag(prefix+'.'+k, True)],
            'max_gb': float(setting(prefix+'.max_gb', '30' if prefix == 'movie' else '8')),
            'screeners': flag('screeners', True), 'unknown_size': flag('unknown_size', True),
            'unknown_quality': flag('unknown_quality', False),
            'hdr': flag('hdr', True), 'dv': flag('dv', False),
            'hevc': flag('hevc', True), 'av1': flag('av1', False), 'ready_only': flag('ready_only')}
