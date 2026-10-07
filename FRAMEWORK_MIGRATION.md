# Lumen 0.2.0 framework migration

This is an original-code implementation informed by the module boundaries of FENLightPlus, not a copied or renamed fork. The inspected FENLightPlus main tree had no named license file or license declaration in addon.xml; it did not supply default TMDB or Trakt application credentials. No upstream Python, images, identity or application keys have been bundled.

## Implemented in this stage

- Explicit allowlisted routes separate plugin entry handling from GUI actions.
- Account setup buttons inside Kodi's native settings: TMDB, Trakt application setup and activation, MDBList, Real-Debrid, TorBox, Premiumize, AllDebrid, list selection and disconnection.
- Cancelable Trakt device authorization with server intervals, bounded expiry, pending/denial handling, rate-limit backoff and verification-host validation. Existing refresh handling remains in the account API layer.
- A recovery menu reachable after leaving the dashboard or selectable as startup navigation. Settings can open without importing the dashboard.
- Editable device starting presets for Shield Pro, older Shield and Galaxy Ultra; these do not detect hardware or guarantee codec support.
- Back through TV seasons/episodes and list collections before closing the dashboard.
- Cache clearing limited to discovery and source searches. Accounts, local resume, watchlists, providers and arrival provenance are retained.
- Credential-free account/setup status and failure reports.
- Original dashboard styling, quality controls, sources, trailers, rescraping, source adapters and verified-arrival logic retained.

## Regression and security review

Twenty-eight offline checks passed: 24 add-on behavioral/GUI-boundary tests and 4 packaging tests. Added route rejection, preset isolation, cache preservation, device-activation pending/cancel/denial cases, localization/action-route validation, nested Back and recovery-mode tests. Compilation, XML and package integrity checks supplement them.

A targeted static review covered the changed production modules, route invocation, network helpers, credential writes, source-adapter imports and ZIP publication. Production code contains no eval/exec call, shell launcher or remotely downloaded Python execution. HTTPS-only API calls block authorization forwarding on redirects. Provider modules are explicitly selected installed code, not sandboxed; CocoScrapers and its dependencies have not received a complete audit. Credentials are stored in a device-local file with best-effort permissions, not encrypted. No complete malicious-code-free guarantee is made.

## Still pending

Live Kodi 21.3 rendering, installation, service authorization, playback, performance and the new settings action dispatch must be confirmed on a device. Full FENLightPlus feature parity is not implemented: cloud management, download manager, autoplay/binge, skip-intro, broader tracking providers and full service coverage remain separate work. Real-Debrid activation remains manual API-token entry, TorBox/Premiumize/MDBList use personal keys, and AllDebrid playback remains pending. No shared application keys are supplied. This stage does not implement a global debrid arrival feed. Repository visibility was separately changed to public by its owner.

The migration was merged to main after offline and GitHub Actions checks passed. The repository is public and its feed distributes the 0.2.0 development package. Kodi can install it from Lumen Repository or directly from its ZIP. Live device checks remain pending; earlier numbered packages are retained for manual rollback.

## Device check

1. Install `plugin.video.lumen-0.2.0.zip` over Lumen. Do not delete userdata.
2. Open Information → Configure; verify all eight categories and the account buttons.
3. Apply a device preset if wanted, then customize its quality/size values.
4. Configure your own service accounts. Trakt requires your registered Lumen app details.
5. Open Lumen; verify dashboard tabs and context actions. Open a show → season → episode; Back should return through its parent pages.
6. Select Recovery menu under Tools and recovery → Startup navigation to test setup navigation independently.
7. Check Status and Clear caches; verify accounts, watchlist and resume still exist.
8. Report the credential-free failure report for problems. Never send account files or tokens.

References: https://github.com/thejason40/FenLightPlus and Kodi's documented add-on settings schema at https://kodi.wiki/view/Add-on_settings_conversion. Trakt API documentation: https://trakt.docs.apiary.io/.
