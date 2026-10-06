# Lumen 0.1.0 — Kodi 21 development build

This is an installable-format development ZIP, not the completed production add-on. It contains original readable Python/XML source and a native cinematic dashboard. Kodi installation/rendering, real accounts, real CocoScrapers searches, and playback have **not** been validated on a device. Start on the Shield TV Pro and keep your current working add-on until testing succeeds.

## Install

1. Download **plugin.video.lumen-0.1.0-dev.zip** to the Shield or copy it there from your computer. Do not unzip it for Kodi installation.
2. In Kodi 21.3, open Settings → System → Add-ons → Unknown sources. Enable this to permit a personal ZIP installation.
3. Open Add-ons → Install from zip file and select this ZIP.
4. Open Video add-ons → Lumen. The dashboard opens when Lumen is selected; this version does not automatically launch its dashboard every time Kodi starts.
5. Open **Accounts**. Configure TMDB first for catalog/artwork. Connect your debrid account(s). Configure Trakt/MDBList only if wanted.
6. Install **CocoScrapers** separately using its official project: https://github.com/CocoJoe2411/repository.cocoscrapers (installation source: https://cocojoe2411.github.io/). No scraper or repository installer is bundled with Lumen. Install its required dependencies through Kodi as needed.
7. In Lumen → **Providers → Select CocoScrapers providers**, choose a small set initially. The adapter contract was inspected against CocoScrapers **1.0.32**; other versions may need adaptation. This inspection was not a full module security audit. Lumen uses the selected provider subset, which is independent of CocoScrapers's own master selection switches; its per-provider settings still apply.
8. Open Settings and set your local device name, movie/episode resolutions and size limits. Defaults are demonstration starting values, not hardware detection: movies 30 GB; episodes 8 GB; all four resolution choices enabled. Tune the phone and older Shield separately.
9. Choose **Refresh**. The Today page only shows sources confirmed available within the configured candidate pool. No fictional movie titles or sample sources are shipped.

If Kodi reports a dependency/install error or the dashboard fails to open, capture the exact message and Kodi version. Do not share API keys, account files, signed playback URLs, or an unredacted Kodi log.

## Accounts

| Service | Setup in this build | Implemented capability; live validation pending |
|---|---|---|
| TMDB | Enter your own API key or read-access token from https://www.themoviedb.org/settings/api | Catalog, artwork, seasons/episodes, trailer lookup |
| Real-Debrid | Enter your personal API token from https://real-debrid.com/apitoken | Account validation, downloaded account-torrent availability, selected torrent/file resolution, hoster link unrestrict |
| TorBox | Enter your API key from the TorBox settings page | Account validation, known-hash cached checks, selected cached torrent/file playback resolution |
| Premiumize | Enter your API key from the Premiumize account page | Account validation, cached checks, direct download resolution |
| AllDebrid | PIN activation or API key | Account validation and ready account-torrent checks; **playback not implemented** |
| Trakt | Register a personal Lumen API app, enter its client ID/secret locally, then activate with a device code | List selection, watch history, watchlist additions, token refresh, playback-progress lookup, optional scrobbling |
| MDBList | Enter your own API key | Account validation, selected-list browsing and candidate references |

Open **Accounts → Disconnect an account** to remove credentials from this device. Disconnection does not revoke API keys at the service; revoke them there if needed. Trakt and MDBList connect independently; MDBList currently states that direct Trakt sync is unavailable.

For Trakt, register at https://trakt.tv/oauth/applications using a Lumen personal app name and the out-of-band redirect URI `urn:ietf:wg:oauth:2.0:oob`. Enter the returned client ID and client secret under **Accounts → Trakt application setup**. The activation flow and refresh require the application registration. No FENLightPlus application keys are reused. If Trakt no longer accepts that registration/URI for your app, stop and report the registration message so the flow can be adjusted to its current requirements.

Use Accounts → **Select MDBList/Trakt widget lists** to select multiple lists. Enable the corresponding Settings toggle. You can restrict the refresh candidate pool to those lists. MDBList's own dynamic-list refresh schedule and account limits still apply; reloading Kodi cannot force MDBList to regenerate its upstream list.

## Navigation and context actions

- The first tab is **Today**, with first-found or newly-available badges. Movies and TV Shows also offer metadata discovery. They are not proof of playable availability. Episodes shows recently verified episode candidates. Collections groups selected lists; collection-wide completeness checking is pending.
- Click a TV show to choose a season, then an episode. Back currently closes the dashboard rather than maintaining a complete nested-navigation history; reopen a tab to return to its top level.
- On a focused movie/episode, use the Kodi context-menu action: right-click, phone long-press, or the remote's configured context/menu action. Choose **Select trailer source**, **Rescrape sources**, or **Rescrape options**. A TV-show context action opens trailer selection; select an episode before searching episode sources.
- Trailer selection uses TMDB video entries with a YouTube provider/language/quality label. Install/configure Kodi's official YouTube add-on separately to play them. Other trailer sites are not implemented yet.
- Rescrape bypasses Lumen's search cache. It does **not** bypass internal caches in CocoScrapers/provider sites. Use CocoScrapers's own settings when those need clearing.
- Rescrape options let you select services/modules or temporarily show unknown availability/resolution. Temporary changes do not modify the saved profile. Saved quality settings can also be opened explicitly.
- You get a short recommended source list followed by More Sources. Availability Unknown means the service could not confirm readiness; it does not mean the file is absent everywhere.
- Real-Debrid may need to add/download a selected torrent. A confirmation names that action; no bulk candidates are added during refresh. TorBox's selected-source addition requests cached-only behavior. Premiumize resolves directly without a cloud transfer.

## Today and refresh behavior

Startup and explicit reload/Refresh trigger bounded refreshes when enabled, with a 15-second rapid-refresh debounce and documented API backoff. Saved content paints first. The default batch is six titles/episodes, two provider workers, and a 20-second provider search budget **per title**. A full batch may therefore take minutes in the background. Reduce it on the older Shield/phone if needed.

CocoScrapers supplies title searches, not an all-server new-arrivals inventory. In this build the candidate pool comes from selected lists and trending catalog titles, with up to two latest-aired episodes from trending shows. Source publication/RSS ingestion, TorBox Search API discovery, followed-show Up Next, and global source-arrival coverage are pending. The feed is the newest verified sources found **within this limited pool**, not every release that day.

The first scan labels existing content **First Found**. Subsequent newly observed candidates can be labeled Newly Available. Dates use the device's local timezone. The same source returning later keeps its original first-found time within the retained index. Checks expire after one hour; selected sources are resolved again for playback. The observation index retains at most 2,000 records, so eviction means historical first-found dates are no longer known. A source matching a cached torrent still needs a valid matching video file at selection time.

Real-Debrid checks only downloaded torrents in the first 100 account entries; AllDebrid checks ready account torrents. Neither performs a global cache search. TorBox and Premiumize check known hashes. Accounts can therefore have different coverage for the same candidates. Ready-to-watch evidence is provisional until file selection/resolution succeeds.

No local server is required. Refresh runs only while this add-on invocation is active; no scheduled refresh happens while Kodi is off. Source-arrival timestamps remain local per device. Trakt progress sync does not sync the availability index.

## Watch progress

Local playback resume is recorded for Lumen-launched playback by the installed playback service. A digest/time check prevents unrelated Kodi playback from being attributed to Lumen. Trakt remote resume is requested when connected. **Trakt scrobbling is off by default**: enable it after disabling another tracker for this playback to avoid duplicate reports. Offline local progress persists; failed Trakt events are not automatically replayed. Full offline reconciliation and Up Next are pending.

## Security and footprint

Runtime dependency: Kodi's Python 3 API only. CocoScrapers and YouTube are separately managed optional external add-ons with their own dependencies. There is no browser runtime, third-party repository installer, telemetry, referral injection, unsolicited log upload, remote script loader, cloud deletion, or automatic Lumen update in this package.

Credentials are in the device's Lumen profile `accounts.json` with owner-only filesystem permissions where supported. **They are not encrypted by this build.** Android/Kodi or anyone with access to that profile may read them. Do not share that file or your Kodi profile. This package has no credential export. API errors shown by Lumen omit URLs/tokens; Kodi or external modules may maintain their own logs.

External Python modules run with Kodi permissions. The adapter interface does not sandbox them. Register only locally installed code you trust. Additional adapters whose version changes must be re-registered after review. No claim of guaranteed malicious-code absence or a complete security audit is made.

## Development status

The browser concept had 94 preferences. This initial native build has **33 operative settings** and does not claim parity with the full concept or FENLightPlus. Remaining work includes AllDebrid playback, additional debrid adapters (Offcloud/EasyDebrid/etc.), service device-authorization refinements, source publication feeds, per-widget sorting/filter modes, franchise/complete-collection availability, robust nested Back behavior, artwork cache limits, offline Trakt reconciliation, and full phone/remote layout testing. These are implementation gaps, not hidden simulated integrations.

Offline checks passed for Python compilation, XML parsing/settings IDs/navigation references, quality/type filters, deduplication, episode matching, availability handling, credential separation, and selected-source mutation confirmation. See VALIDATION.md. **No successful Kodi installation, rendering, authorization, source search, or video playback has been observed.**

## First-device test

1. Confirm installation and dashboard rendering on Shield Pro/Kodi 21.3.
2. Configure your catalog key, one debrid account and a small provider subset.
3. Check Refresh details for partial errors. Verify that Unknown never gets a confirmed badge.
4. Select a title you have rights to access, open its context menu, inspect trailers, rescrape and source options.
5. Test movie playback, pause/seek/stop/resume, then an individual episode and a pack with explicit episode filenames.
6. Test with a canceled search, an expired/invalid token, network loss and a title with no sources.
7. Only after those work, connect Trakt/MDBList and test private lists, watched history and cross-device progress.
8. Repeat on the older Shield and phone with separate local quality settings.

Report the exact error plus device/Kodi/skin and step number. Share credentials only with the corresponding service inside its authorization flow.

## Remove / roll back

Kodi → Add-ons → My add-ons → Video add-ons → Lumen → Uninstall. Remove its profile data when Kodi offers that option if you want to erase saved credentials and observations. There is no previous Lumen release to roll back to; your existing unrelated add-ons/build are not replaced. Reinstalling this same ZIP does not clear profile data by itself.
