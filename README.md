# Lumen for Kodi 21.3 Omega

Personal development video add-on with a native cinematic dashboard, CocoScrapers adapter, service integrations, list widgets and device-specific playback preferences.

**Development build: device installation, rendering, live authentication and playback are not yet validated.** See [setup and limitations](plugin.video.lumen/INSTALL.md) and [validation](plugin.video.lumen/VALIDATION.md). No account keys or third-party scraper archives are included.

## Downloads

- [Lumen 0.3.0 development ZIP](repo/plugin.video.lumen/plugin.video.lumen-0.3.0.zip)
- [Lumen Repository 1.0.1 ZIP](repo/repository.lumen/repository.lumen-1.0.1.zip)
- [Kodi repository installation and updates](KODI_REPOSITORY_SETUP.md)

The repository ZIP points at this project's public `main/repo/` distribution feed. Kodi can download its index and packages without a GitHub login. No account credentials are included in the installer or source.

## Publishing a revision

1. Edit the original source under `plugin.video.lumen/`.
2. Increase `version` in `plugin.video.lumen/addon.xml`, for example `0.1.0` to `0.1.1`. Never replace a published version with different code.
3. Run `python3 -m unittest discover -s plugin.video.lumen/developer -q` and `python3 -m unittest discover -s tools -q`.
4. Run `python3 tools/build_repository.py`. Commit the source, regenerated manifest and `repo/` files together.
5. Alternatively the included GitHub Actions workflow runs these tests and publishes the generated feed after source changes on `main`, provided GitHub allows the workflow and its write permission. Check its run result before claiming publication.
6. Kodi receives the latest **packaged, higher-version** revision when it next checks for updates and the feed is accessible. A plain source edit without a version increase is deliberately rejected.

The builder uses Python's standard library, deterministic ZIPs, version immutability checks and SHA-256 inventories. HTTPS protects delivery. The `.md5` index file is only Kodi's feed change marker; hashes are not independent signatures or a full security audit. GitHub raw hosting does not provide Kodi's `content-sha256` HTTP header, so the repository uses `hashes=false` rather than claiming that Kodi checks that header.

Private hosting can instead use a separately designed authenticated updater or public distribution-only repository. Neither is silently enabled by this package.

## Framework migration

The 0.2.0 original-code framework migration is published on main as a development update. See [implemented changes and remaining work](FRAMEWORK_MIGRATION.md). Its offline checks passed; device installation, rendering, live authentication and playback still need confirmation. Earlier numbered packages remain available for manual rollback.

### 0.2.1 startup fix

Corrected a router import that ran before the add-on library path was initialized. Added two fresh-interpreter entrypoint regression tests that fail against 0.2.0 and pass against this patch. Install the 0.3.0 ZIP directly for immediate recovery if Kodi still offers a cached older package. Device confirmation is still required.

### 0.3.0 Release Radar

Native RSS/Atom and configurable JSON announcement discovery runs inside Kodi, without an external server. Cached Latest Releases, Movies, Episodes, 4K/HDR and Trailers views open without feed requests. Add permitted public HTTPS sources through Settings → Release Radar → Manage announcement sources and cache. There are no preconfigured feeds. Connect your own TMDB key for metadata; unmatched announcements can be matched manually before playback.

Announcements and first-seen dates do not imply debrid availability. Ready to Watch retains the existing, separately verified availability view; selecting a matched title uses the existing source modules and debrid playback layer. Existing AllDebrid playback and other framework limitations remain. See [Release Radar setup, adapter format and limits](plugin.video.lumen/RELEASE_RADAR.md).
