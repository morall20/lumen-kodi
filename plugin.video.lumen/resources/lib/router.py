"""Explicit routes: no eval, remote imports or arbitrary callable names."""
from urllib.parse import parse_qs

ROUTES = frozenset(('home', 'accounts', 'providers', 'settings', 'account',
                    'device', 'status', 'clear_cache', 'trakt_setup', 'radar'))


def parse(argv):
    query = argv[2] if len(argv) > 2 else ''
    if len(query) > 8192:
        raise ValueError('Route is too long')
    values = parse_qs(query.lstrip('?'), max_num_fields=20)
    action = values.get('action', ['home'])[0]
    if action not in ROUTES:
        raise ValueError('Unknown Lumen route')
    return action, {key: value[0] for key, value in values.items() if key != 'action'}


def dispatch(action, params, handlers):
    if action not in ROUTES or action not in handlers:
        raise ValueError('Unknown Lumen route')
    return handlers[action](params)
