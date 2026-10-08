# Release Radar — Lumen 0.3.0

Release Radar is a native Kodi subsystem. No external process or server is needed, and no discovery feeds, keys or scraper code are bundled.

## Setup

1. Install Lumen 0.3.0, restart Kodi, and open Lumen Settings → Release Radar.
2. Choose Manage announcement sources and cache → Add RSS/Atom feed or Add permitted JSON API. Enter a display name and a public HTTPS endpoint you are permitted to query. Maximum four enabled/configured endpoints; one response page per endpoint. Authentication headers and credential-bearing URLs are not supported; do not put tokens or keys in an endpoint URL. Source configuration lives in local Kodi SQLite state.
3. Connect TMDB through Accounts for metadata. Existing debrid accounts and installed source modules are configured separately and used only in the playback/provider flow.
4. Select Refresh announcements now. Automatic refresh defaults to 30 minutes, configurable from 5 to 1440. Manual refresh can bypass the TTL but has a 60-second cooldown. Both Kodi's service and Lumen's dashboard use a database lease to avoid overlapping refreshes. Opening a cached view does not fetch a feed.
5. Use Latest Releases for today's separately verified Ready entries followed by announcements, Ready to Watch for recently checked available titles, or Release Radar for announcements plus those Ready entries. Movies and Episodes use cached announcements with existing cached discovery/availability fallback. TV Shows uses saved TV discovery. 4K/HDR selects 2160p or HDR/DV announcements. Trailers opens the trailer-source selector when a title is selected; YouTube playback requires the separately installed Kodi YouTube add-on.

The dashboard keeps its existing visual assets and adds a compact second navigation row. It opens when Lumen is selected. The service refreshes Radar at Kodi startup/while Kodi runs; it does not forcibly open a window when Kodi starts.

## Settings and caching

Radar settings include enable/disable, Movies/TV toggles, interval, minimum resolution (SD/unknown, 720p, 1080p, 1440p/2K, 2160p/4K), preferred resolution, and HDR/DV inclusion. Metadata language uses Lumen's existing Interface → Language setting. These are discovery preferences; existing per-device movie/episode playback filters still control playable source choices. Preferred resolution breaks ties between same-time announcement variants; newest announcements retain priority.

Announcements, daily TMDB metadata, conditional HTTP validators and refresh state use tables in the existing local lumen.db. Up to 2000 announcements and 2000 metadata records are retained. Artwork URLs are stored in metadata and Kodi manages downloaded artwork; Radar does not periodically download or delete images. Clearing Radar cache removes first-seen history, announcements, metadata and validators. It preserves feed configuration, credentials, watchlists, playback resume and source-module settings. Clearing discovery/search caches in Tools does not clear Radar.

A refresh fetches at most four responses, 50 announcements per response, and attempts metadata for at most eight eligible records. Each response is limited to 1 MiB, with an 8-second network socket timeout, no redirects, no DTD/entities and no execution of returned content. A cooperative 60-second work budget stops new work; an in-flight request may finish after that budget. Kodi abort/window-close is checked between requests. Failed feeds preserve cached results and do not advance HTTP validators. Metadata enrichment continues in later refreshes; a large first import will not immediately have artwork on every record. See Radar status for partial failures, without API tokens, endpoint URLs or exception text.

Existing startup provider/availability checks now honor the Radar interval rather than rescraping on every Lumen launch. Manual dashboard Refresh requests both a Radar refresh and the existing bounded provider refresh. The service refreshes announcement/metadata discovery only, without adding anything to debrid accounts.

## JSON API adapter

Configure dotted object-field paths in Kodi. Default fields are items, title and published. Use a blank items field for a root array. Optional tmdb/imdb/tvdb field paths avoid title searches; TV episode announcement IDs must refer to the **show**, not the episode. Dates must be ISO 8601 or RSS-style dates. Array indexing, pagination, site JavaScript, HTML parsing, custom headers and authenticated feed APIs are not implemented.

For an API response shaped like:

```json
{"data":{"releases":[{"name":"Example.Movie.2026.2160p.WEB-DL.HEVC-GROUP","announced":"2026-10-08T12:00:00Z","ids":{"tmdb":123}}]}}
```

enter items field `data.releases`, title field `name`, date field `announced`, and optional TMDB field `ids.tmdb`. A source may include page/playback links, hashes or enclosures; these are discarded. Only title, announcement date and validated external IDs are consumed. Configurable JSON mappings provide site adapters without remotely supplied executable modules; HTML scraping requires a separate reviewed implementation.

## Identity and availability

The parser extracts title/year, SxxExx or NxEE episode identity, resolution, WEB-DL/WEBRip/BluRay/DVD/DVDRip/screener/stream type, HDR/DV, HEVC/AVC/AV1, basic audio and release group. Release names are inconsistent; season packs, multi-episode and date-based names are not reliably handled. Some titles containing years/technical terms require manual matching. Automatic movie matching requires a unique exact normalized title and year; TV requires a unique exact show title. Ambiguous/unmatched records stay visible as announcements. Selecting one offers a manual metadata search and confirmation, then the existing source selector. A confirmed identity is retained for later daily metadata refreshes.

TMDB detail data includes external IDs, poster/fanart, synopsis, genres, cast, runtime, certifications and supported trailers. Existing Trakt/MDBList libraries and playback synchronization remain available through My Lists. Their added/viewed timestamps retain their existing meaning; they are not interpreted as release-announcement or server-arrival dates. This update does not add a new Trakt watchlist synchronization implementation.

**Announced** means a feed publisher supplied a date; **First seen** means Lumen observed an undated announcement on this device. Neither proves that a debrid server has the file or that its quality is accurate. Ready to Watch uses the existing provider/debrid checks and their bounded coverage. Feed links never become playable candidates; selecting a matched title invokes configured installed source modules and existing debrid adapters independently. AllDebrid account activation remains available but its playback implementation is still pending. No global newest-arrival feed from debrid servers is claimed.

## Validation

46 add-on behavioral checks and 4 packaging checks pass offline, including parsing, RSS/Atom/JSON ingestion, conservative movie/episode identity, daily metadata caching, source limits, no playback calls during Radar refresh, TTL/concurrent leases, cancellation, HTTP validators, quality filters and cache preservation. Live feeds, authentication, skin rendering, Shield/phone navigation and actual playback are not tested on Kodi hardware in this environment.
