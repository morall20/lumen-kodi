"""Parse announcement names only. Never extract playback links."""
import re
import unicodedata


def normalized(value):
    value = unicodedata.normalize('NFKD', str(value)).casefold()
    return ''.join(c for c in value if c.isalnum() and not unicodedata.combining(c))


def parse(name):
    raw = str(name).strip()[:500]
    raw = re.sub(r'\.(mkv|mp4|avi|mov|m4v)$', '', raw, flags=re.I)
    scan = raw.replace('_','.')
    episode = re.search(r'(?i)\bS(\d{1,2})[ ._-]*E(\d{1,3})\b', scan)
    if not episode:
        episode = re.search(r'(?i)\b(\d{1,2})x(\d{1,3})\b', scan)
    year = re.search(r'(?<!\d)((?:19|20)\d{2})(?!\d)', raw)
    quality = re.search(r'(?i)\b(2160p|1440p|1080p|720p|480p|4K|2K)\b', scan)
    source = re.search(r'(?i)\b(WEB[ ._-]?DL|WEB[ ._-]?RIP|BLU[ ._-]?RAY|BDRIP|BRRIP|DVD[ ._-]?RIP|DVD[ ._-]?SCR|DVDSCREENER|SCREENER|HDRIP|HDTV|STREAM|DVD)\b', scan)
    markers = [m.start() for m in (episode, year, quality, source) if m]
    title = raw[:min(markers)] if markers else raw
    title = re.sub(r'[._]+', ' ', title).strip(' -()[]')
    src = re.sub(r'[ ._-]', '', source.group(0)).upper() if source else 'Unknown'
    src = {'WEBDL':'WEB-DL', 'WEBRIP':'WEBRip', 'BLURAY':'BluRay', 'DVDRIP':'DVDRip',
           'DVDSCR':'Screener', 'DVDSCREENER':'Screener', 'SCREENER':'Screener', 'STREAM':'Stream'}.get(src, src)
    q = quality.group(0).upper() if quality else ''
    resolution = {'4K':'2160p', '2K':'1440p'}.get(q, q.lower())
    audio = re.search(r'(?i)\b(DDP|EAC3|AC3|DTS(?:[ ._-]?HD)?|TRUEHD|AAC|DD)([ ._-]?[257]\.1)?\b', scan)
    group = re.search(r'-([A-Za-z0-9][A-Za-z0-9_]{1,39})$', raw)
    codec = 'HEVC' if re.search(r'(?i)\b(HEVC|H[ .]?265|X265)\b', scan) else 'AVC' if re.search(r'(?i)\b(AVC|H[ .]?264|X264)\b', scan) else 'AV1' if re.search(r'(?i)\bAV1\b', scan) else ''
    return {'title':title, 'year':year.group(1) if year else '',
            'media_type':'episode' if episode else 'movie',
            'season':int(episode.group(1)) if episode else None,
            'episode':int(episode.group(2)) if episode else None,
            'resolution':resolution, 'source':src,
            'audio':audio.group(1).upper()+' '+audio.group(2).strip(' ._-') if audio and audio.group(2) else audio.group(1).upper() if audio else '',
            'dolby_vision':bool(re.search(r'(?i)\b(DV|DOVI|DOLBY[ ._-]?VISION)\b', scan)),
            'hdr':bool(re.search(r'(?i)\bHDR(?:10\+?)?\b', scan)),
            'codec':codec, 'releasegroup':group.group(1) if group else '', 'name':raw}
