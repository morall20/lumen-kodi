# Lumen external adapter contract

Install a normal Kodi Python module add-on with an `xbmc.python.module` extension and a `lib` directory. Register its installed add-on ID and Python import module through Lumen → Providers. The module must provide:

```python
def search(media, deadline):
    # deadline: monotonic timestamp; respect it and set network timeouts.
    # media: type, id, title, year, imdb; episodes also carry
    # show_id, show_title, season, episode. No account credentials.
    return [{
        "name": "release name with source/resolution attributes",
        "url": "magnet:?xt=urn:btih:...",  # or supported https hoster URL
        "hash": "40-character hex infohash",  # optional for URL sources
        "size": 1.5,  # gigabytes; 0 means unknown, not an empty file
        "quality": "1080p",
        "provider": "your provider name",
    }]
```

This build runs the registered adapters and selected CocoScrapers providers through one coordinator with two active workers. Results merge by hash/URL and file identity when present; provenance is retained. Do not return multiple different torrent-file variants under the same hash without explicit file identity; per-file identity normalization needs extension before doing so. Pack support is conservative: playback selection requires the exact episode filename.

Use cooperative deadlines, HTTPS, finite reads, explicit media-ID matching, and no credential logging. A blocked Python worker cannot be forcibly killed safely. Lumen prevents a second search in the same invocation while old workers finish, but separate Kodi invocations are not a security sandbox or an enforced process-wide quota. Only enable finite, inspected implementations.

Do not place a remote script URL in these fields. Lumen imports locally installed module code only. Code runs with Kodi permissions; registration is an explicit trust decision. The retained add-on version must match before reuse. Multiple different registered adapters can be enabled simultaneously.

Debrid services are a separate adapter layer in `resources/lib/accounts.py`. Additions require documented authentication, account validation, availability semantics, selected-source resolution, disconnect behavior, failure handling, fixture tests and live tests. Adding a service name or token field alone does not establish support. Current source URL support is limited to resolvers that accept that URL; there is no generic arbitrary streaming-site extractor.
