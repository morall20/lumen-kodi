import ipaddress
from urllib.parse import urlparse
from urllib.request import Request, build_opener
from urllib.error import HTTPError, URLError
from runtime import NoRedirect, ApiError

MAX_BYTES = 1024 * 1024


def validate_url(url):
    p = urlparse(str(url))
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.fragment or p.port not in (None,443):
        raise ValueError('Use a public HTTPS endpoint without credentials or fragments')
    host = p.hostname.lower()
    if host=='localhost' or host.endswith(('.localhost','.local','.internal')) or '.' not in host:
        raise ValueError('Use a public HTTPS endpoint')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and not address.is_global:
        raise ValueError('Use a public HTTPS endpoint')
    return str(url)


def fetch(url, validators=None):
    validate_url(url)
    headers={'User-Agent':'Lumen-ReleaseRadar/1','Accept':'application/atom+xml,application/rss+xml,application/json,application/xml'}
    for key in ('If-None-Match','If-Modified-Since'):
        value=(validators or {}).get(key)
        if value and '\r' not in value and '\n' not in value:
            headers[key]=value[:500]
    try:
        with build_opener(NoRedirect()).open(Request(url,headers=headers),timeout=8) as response:
            raw=response.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES:
                raise ValueError('Feed exceeds 1 MiB limit')
            tags={}
            for name,key in [('ETag','If-None-Match'),('Last-Modified','If-Modified-Since')]:
                if response.headers.get(name):
                    tags[key]=response.headers[name][:500]
            return raw,tags
    except HTTPError as error:
        if error.code==304:
            return None,validators or {}
        raise ApiError(error.code,'radar_feed') from None
    except (URLError,OSError,TimeoutError):
        raise ApiError(0,'radar_network') from None
