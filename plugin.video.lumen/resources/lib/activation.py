"""Bounded, cancelable Trakt device authorization using a personal app."""
import time
from urllib.parse import urlparse
from runtime import request, ApiError


def activate_trakt(app, show_code, canceled, wait, clock=time.monotonic):
    if not app.get('client_id') or not app.get('client_secret'):
        raise ApiError(401, 'application_setup_required')
    data = request('https://api.trakt.tv/oauth/device/code', 'POST',
                   data={'client_id': app['client_id']})
    verification = urlparse(data.get('verification_url', ''))
    if verification.scheme != 'https' or verification.hostname not in ('trakt.tv', 'www.trakt.tv'):
        raise ApiError(0, 'invalid_verification_host')
    interval = max(1, int(data['interval']))
    duration = min(1800, max(1, int(data['expires_in'])))
    deadline = clock() + duration
    show_code(data['verification_url'], data['user_code'])
    while clock() < deadline:
        if canceled() or wait(min(interval, max(0, deadline - clock()))) or canceled():
            return None
        if clock() >= deadline:
            break
        try:
            token = request('https://api.trakt.tv/oauth/device/token', 'POST',
                            data={'code': data['device_code'], 'client_id': app['client_id'],
                                  'client_secret': app['client_secret']})
        except ApiError as error:
            if error.status == 400:  # device authorization pending
                continue
            if error.status == 429:
                interval = max(interval + 5, error.retry)
                continue
            raise
        if not token.get('access_token') or not token.get('refresh_token'):
            raise ApiError(0, 'invalid_token_response')
        token.setdefault('created_at', time.time())
        return token
    raise ApiError(410, 'activation_expired')
