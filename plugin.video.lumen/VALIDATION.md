# Lumen 0.1.0 validation

Checked October 6, 2026 in Python 3 with mocked Kodi/API boundaries. Python bytecode compilation passed. Twelve behavioral tests passed:

1. Resolution separate from source type, including 4K/2K/1080p/720p.
2. Device-local movie/episode limits and CAM exclusion.
3. Exact episode-file matching excludes another episode and non-video files.
4. Hash deduplication preserves provenance; case-sensitive URLs remain distinct.
5. Unknown availability does not become confirmed readiness.
6. Returning sources retain first-found time and baseline flag.
7. API failure yields partial error/unknown state.
8. Rejecting a selected-source cloud-add confirmation causes no mutation.
9. Credentials remain outside the availability database and disconnect removes them.
10. API HTTP/redirect rejection protects credentials from forwarding.
11. List membership does not invent availability or list-added dates.
12. Manifest, setting identifiers, quality options and XML navigation references.

Tests use fixtures only. They do not assert that service APIs currently accept every payload, that third-party modules are safe, or that the UI loads on Kodi. Kodi is not available in the build workspace, and no live credentials were provided. Installation, visual rendering, remote/touch navigation, authentication, provider searches, playback/resume, cross-device Trakt sync, network failure behavior and hardware performance all remain unverified.

Run the included offline tests from this add-on's extracted directory:

```sh
python3 -m unittest discover -s developer -v
```

No sample films or accounts are installed by these tests. Kodi imports are stubbed for the test process only.

## References used for independently written integration code

- Kodi settings format: https://kodi.wiki/view/Add-on_settings_conversion
- CocoScrapers 1.0.32 module archive from https://github.com/CocoJoe2411/repository.cocoscrapers (entry points inspected as text, not executed).
- Real-Debrid API: https://api.real-debrid.com/
- TorBox API: https://api-docs.torbox.app/ and official SDK documentation https://github.com/TorBox-App/torbox-sdk-js
- Premiumize API: https://www.premiumize.me/api
- AllDebrid API: https://docs.alldebrid.com/
- Trakt API: https://trakt.docs.apiary.io/ and https://developer.trakt.tv/docs/api-use-policy
- MDBList API: https://api.mdblist.com/docs/
- TMDB API: https://developer.themoviedb.org/reference

FENLightPlus was used earlier as a feature reference, not as bundled executable code or a source of account/app keys. No external scraper archive is redistributed in this ZIP.

## 0.1.1 startup/settings correction

The first device report described a load failure and a blank settings window. Renamed the dashboard to `script-lumen-home.xml` because Kodi checks the active skin before the add-on fallback; `Home.xml` can load the skin home window with incompatible controls. Replaced category/setting labels with numeric localization IDs and bundled English strings. Added credential-free failure reports, guarded dashboard initialization, and settings routing that does not import the dashboard. These defects were identified from source; the user crash log was not available. The corrected ZIP still requires on-device confirmation. Repository hosting remains private pending owner approval.

## 0.2.0 framework stage

24 add-on behavioral checks plus 4 repository packaging tests pass offline. Added explicit-route rejection, device preset credential isolation, cache preservation, Trakt pending/cancel/denial behavior, settings action mapping, recovery mode and nested Back tests. This does not establish live Kodi/API compatibility or complete FENLightPlus feature parity. See FRAMEWORK_MIGRATION.md for the targeted review and device-check scope.

## 0.2.1 entrypoint correction

Fresh isolated Python interpreter tests reproduced ModuleNotFoundError for the router on both home and settings entry routes in 0.2.0. Its import occurred before the add-on library path was added. Moved the import inside the guarded launch after path setup. Both new entrypoint tests pass alongside the existing 24 add-on tests and 4 packaging tests (30 total). GUI/API boundaries are still mocked; live Kodi device validation remains required. The home entrypoint test validates dispatch with a stub application, while separate GUI-boundary tests exercise the dashboard.
