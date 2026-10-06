"""Pure source normalization and filtering; no Kodi dependency."""
import base64
import re
import time
from urllib.parse import parse_qs, urlparse

VIDEO_EXT = ('.mkv', '.mp4', '.avi', '.mov', '.m4v', '.ts', '.webm')

def infohash(value):
    value = str(value or '')
    if value.startswith('magnet:'):
        value = next((x[9:] for x in parse_qs(urlparse(value).query).get('xt', []) if x.startswith('urn:btih:')), '')
    if re.fullmatch(r'[a-fA-F0-9]{40}', value):
        return value.lower()
    if re.fullmatch(r'[A-Z2-7a-z]{32}', value):
        try:
            return base64.b32decode(value.upper()).hex()
        except ValueError:
            pass
    return ''

def attributes(name, quality=''):
    text = str(name).upper()
    q = str(quality).upper()
    if re.search(r'\b(2160P|4K|UHD)\b', text + ' ' + q):
        res = '4K'
    elif re.search(r'\b(1440P|QHD|2K)\b', text + ' ' + q):
        res = '2K'
    elif '1080' in text + q:
        res = '1080p'
    elif '720' in text + q:
        res = '720p'
    else:
        res = 'Unknown'
    patterns = [('CAM', r'\b(HDCAM|CAM|TELESYNC|TELECINE|HDTS|TSRIP)\b'),
                ('Screener', r'\b(DVDSCR|SCR|SCREENER)\b'),
                ('WEB-DL', r'WEB[ ._-]?DL'), ('WEBRip', r'WEB[ ._-]?RIP'),
                ('DVDRip', r'DVD[ ._-]?RIP'), ('DVD', r'\bDVD(R|5|9)?\b'),
                ('BluRay', r'BLU[ ._-]?RAY|BDRIP|BRRIP')]
    kind = next((label for label, pat in patterns if re.search(pat, text)), 'Unknown')
    return {'resolution': res, 'source_type': kind, 'hdr': bool(re.search(r'\bHDR\b', text)),
            'dv': bool(re.search(r'\b(DV|DOVI)\b|DOLBY.VISION', text)),
            'hevc': bool(re.search(r'HEVC|H.?265|X265', text)), 'av1': 'AV1' in text}

def normalize(raw, module):
    name = str(raw.get('name') or raw.get('filename') or raw.get('url') or '')[:500]
    url = str(raw.get('url') or '')
    hash_ = infohash(raw.get('hash')) or infohash(url)
    if not hash_ and urlparse(url).scheme not in ('https', 'http'):
        return None
    try:
        size = max(0, float(raw.get('size') or 0))
    except (TypeError, ValueError):
        size = 0
    return dict(attributes(name, raw.get('quality')), name=name, url=url, hash=hash_,
                size_gb=size, modules=[module], provider=str(raw.get('provider') or module),
                availability='unknown', service='', checked=0)

def merge(sources):
    result = {}
    for s in sources:
        # URLs are case sensitive. Different file identities must not be merged.
        key = (s.get('hash') or s.get('url'), s.get('file_id', ''))
        if key in result:
            result[key]['modules'] = sorted(set(result[key]['modules'] + s['modules']))
        else:
            result[key] = dict(s)
    return list(result.values())

def eligible(s, prefs):
    if s['resolution'] not in prefs['resolutions']:
        if not (s['resolution'] == 'Unknown' and prefs.get('unknown_quality')):
            return False
    if s['source_type'] == 'CAM':
        return False
    if s['source_type'] == 'Screener' and not prefs.get('screeners'):
        return False
    if not s.get('size_gb') and not prefs.get('unknown_size', True):
        return False
    if s.get('size_gb', 0) > prefs.get('max_gb', 100):
        return False
    if any(s.get(key) and not prefs.get(key, True) for key in ('hdr', 'dv', 'hevc', 'av1')):
        return False
    if prefs.get('ready_only') and s.get('availability') != 'ready':
        return False
    return True

def rank(s):
    return (s.get('availability') != 'ready',
            {'4K': 0, '2K': 1, '1080p': 2, '720p': 3}.get(s['resolution'], 4),
            s.get('size_gb') or 999)

def video_files(files, media):
    candidates = [x for x in files if str(x.get('path') or x.get('name') or '').lower().endswith(VIDEO_EXT)]
    if media.get('type') == 'episode':
        season, episode = int(media['season']), int(media['episode'])
        pat = re.compile(r'(?:s0*%de0*%d(?!\d)|\b0*%dx0*%d(?!\d))' % (season, episode, season, episode), re.I)
        candidates = [x for x in candidates if pat.search(str(x.get('path') or x.get('name')))]
    return candidates

def observation(previous, now=None):
    now = now or time.time()
    return {'first': previous.get('first', now), 'checked': now,
            'baseline': previous.get('baseline', False)}
