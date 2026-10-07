# Lumen for Kodi 21.3 Omega

Personal development video add-on with a native cinematic dashboard, CocoScrapers adapter, service integrations, list widgets and device-specific playback preferences.

**Development build: device installation, rendering, live authentication and playback are not yet validated.** See [setup and limitations](plugin.video.lumen/INSTALL.md) and [validation](plugin.video.lumen/VALIDATION.md). No account keys or third-party scraper archives are included.

## Downloads

- [Lumen 0.2.0 migration ZIP](repo/plugin.video.lumen/plugin.video.lumen-0.2.0.zip)
- [Lumen Repository 1.0.0 ZIP](repo/repository.lumen/repository.lumen-1.0.0.zip)
- [Kodi repository installation and updates](KODI_REPOSITORY_SETUP.md)

The repository ZIP points at this project's `main/repo/` distribution feed. **While this GitHub repository is private, Kodi cannot fetch that feed using this standard repository ZIP.** It does not contain a GitHub token or reuse a browser login. Manual download through your signed-in GitHub browser remains possible. Making the repository public requires the owner's approval; nothing in this project changes repository visibility.

## Publishing a revision

1. Edit the original source under `plugin.video.lumen/`.
2. Increase `version` in `plugin.video.lumen/addon.xml`, for example `0.1.0` to `0.1.1`. Never replace a published version with different code.
3. Run `python3 -m unittest discover -s plugin.video.lumen/developer -q` and `python3 -m unittest discover -s tools -q`.
4. Run `python3 tools/build_repository.py`. Commit the source, regenerated manifest and `repo/` files together.
5. Alternatively the included GitHub Actions workflow runs these tests and publishes the generated feed after source changes on `main`, provided GitHub allows the workflow and its write permission. Check its run result before claiming publication.
6. Kodi receives the latest **packaged, higher-version** revision when it next checks for updates and the feed is accessible. A plain source edit without a version increase is deliberately rejected.

The builder uses Python's standard library, deterministic ZIPs, version immutability checks and SHA-256 inventories. HTTPS protects delivery. The `.md5` index file is only Kodi's feed change marker; hashes are not independent signatures or a full security audit. GitHub raw hosting does not provide Kodi's `content-sha256` HTTP header, so the repository uses `hashes=false` rather than claiming that Kodi checks that header.

Private hosting can instead use a separately designed authenticated updater or public distribution-only repository. Neither is silently enabled by this package.

## Framework migration branch

The 0.2.0 original-code framework migration is isolated for device testing. See [implemented changes and remaining work](FRAMEWORK_MIGRATION.md). The repository installer points at main; this branch must be merged before its feed is distributed through that installer.
