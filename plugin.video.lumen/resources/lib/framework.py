"""Original framework utilities; state and credentials keep distinct lifetimes."""
from runtime import ADDON, credential, db, LOCK, read, write

DEVICES = {
    'shield_pro': {'name': 'Shield TV Pro', 'movie_size': 30, 'episode_size': 8, '4k': True, '2k': True, 'hdr': True, 'hevc': True},
    'shield_older': {'name': 'Older Shield', 'movie_size': 18, 'episode_size': 5, '4k': True, '2k': True, 'hdr': False, 'hevc': True},
    'galaxy_ultra': {'name': 'Galaxy Ultra', 'movie_size': 6, 'episode_size': 2, '4k': False, '2k': True, 'hdr': False, 'hevc': True},
}


def apply_device(name):
    if name not in DEVICES:
        raise ValueError('Unknown device preset')
    profile = DEVICES[name]
    ADDON.setSetting('device_name', profile['name'])
    for kind in ('movie', 'episode'):
        ADDON.setSetting(kind + '.max_gb', str(profile[kind + '_size']))
        for res in ('4k', '2k', '1080', '720'):
            ADDON.setSetting(kind + '.' + res, str(profile.get(res, True)).lower())
    for key in ('hdr', 'hevc'):
        ADDON.setSetting(key, str(profile[key]).lower())
    ADDON.setSetting('dv', 'false')
    ADDON.setSetting('av1', 'false')


def clear_cache():
    # Preserve credentials, resume, watchlists, adapters and arrival provenance.
    with LOCK, db() as connection:
        connection.execute("DELETE FROM state WHERE key LIKE 'catalog:%' OR key LIKE 'search:%'")


def status():
    rows = ['Lumen ' + ADDON.getAddonInfo('version'),
            'Device: ' + (ADDON.getSetting('device_name') or 'My Kodi device')]
    for key, name in [('tmdb', 'TMDB'), ('trakt', 'Trakt'), ('mdb', 'MDBList'),
                      ('rd', 'Real-Debrid'), ('tb', 'TorBox'), ('pm', 'Premiumize'), ('ad', 'AllDebrid')]:
        account = credential(key)
        configured = bool(account.get('token') or account.get('access_token'))
        rows.append(name + ': ' + ('credentials configured' if configured else 'not configured'))
    rows.append('Providers selected: ' + str(len(read('coco.providers', []))))
    rows.append('Trakt: ' + ('last scrobble failed; local progress retained' if read('sync_status', {}).get('failed') else 'no recorded sync failure'))
    rows.append('Newest Available records: ' + str(len(read('availability', {}))))
    rows.append('Update feed requires publicly accessible hosting; current repository installer has no GitHub authentication.')
    return '\n'.join(rows)
