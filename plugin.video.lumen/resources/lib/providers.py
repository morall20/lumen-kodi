"""Adapter registry. Local installed adapters only; no remote code loader."""
import importlib
import os
import queue
import sys
import threading
import time
import xml.etree.ElementTree as ET
import xbmcaddon
from runtime import read, setting
from core import normalize, merge

ACTIVE = []
GUARD = threading.Lock()

def add_library_paths(addon_id, seen=None):
    seen=seen if seen is not None else set()
    if addon_id in seen or addon_id.startswith('xbmc.'):
        return
    seen.add(addon_id)
    addon=xbmcaddon.Addon(addon_id)
    root=addon.getAddonInfo('path')
    manifest=ET.parse(os.path.join(root,'addon.xml')).getroot()
    for dependency in manifest.findall('./requires/import'):
        try:
            add_library_paths(dependency.attrib['addon'],seen)
        except RuntimeError:
            if dependency.get('optional')!='true':
                raise
    for extension in manifest.findall('extension'):
        if extension.get('point')=='xbmc.python.module':
            lib=os.path.join(root,extension.get('library','lib'))
            if lib not in sys.path:
                sys.path.append(lib)

def coco_providers(allow_version_change=False):
    addon = xbmcaddon.Addon('script.module.cocoscrapers')
    add_library_paths('script.module.cocoscrapers')
    approved=read('coco.approved_version','')
    if approved and addon.getAddonInfo('version') != approved and not allow_version_change:
        raise RuntimeError('CocoScrapers version changed. Review it and select providers again.')
    module = importlib.import_module('cocoscrapers.sources_cocoscrapers')
    return sorted(module.torrent_providers)

def registry():
    # Additional modules implement search(media, deadline) in a separately
    # installed Kodi Python module. Entries are explicitly approved in Providers.
    return read('adapters', [])

def jobs(media):
    jobs_ = []
    if setting('coco.enabled','true') == 'true':
        names = read('coco.providers', [])
        if not names:
            raise RuntimeError('Select CocoScrapers providers in Providers first.')
        available = coco_providers()
        data = {'imdb':media.get('imdb',''), 'title':media['title'], 'year':str(media.get('year','')),
                'aliases':[], 'debrid_service':'', 'debrid_token':''}
        if media['type'] == 'episode':
            data.update(tvshowtitle=media['show_title'], title=media['title'], tvdb=media.get('tvdb',''),
                        season=str(media['season']), episode=str(media['episode']))
        for name in names:
            if name not in available:
                continue
            cls = importlib.import_module('cocoscrapers.sources_cocoscrapers.torrents.'+name).source
            if media['type'] == 'movie' and not cls.hasMovies:
                continue
            if media['type'] == 'episode' and not cls.hasEpisodes:
                continue
            jobs_.append(('CocoScrapers/'+name, lambda cls=cls: cls().sources(dict(data), [])))
    for adapter in registry():
        if not adapter.get('enabled'):
            continue
        addon = xbmcaddon.Addon(adapter['addon_id'])
        if addon.getAddonInfo('version') != adapter['version']:
            raise RuntimeError('Adapter version changed. Review and register it again before use.')
        add_library_paths(adapter['addon_id'])
        module = importlib.import_module(adapter['module'])
        jobs_.append((adapter['addon_id'], lambda module=module: module.search(dict(media), time.monotonic()+20)))
    return jobs_

def search(media, cancel=lambda:False, selected_modules=None):
    global ACTIVE
    with GUARD:
        ACTIVE = [t for t in ACTIVE if t.is_alive()]
        if ACTIVE:
            raise RuntimeError('Previous provider requests are still finishing. Try again shortly.')
    tasks, out = queue.Queue(), queue.Queue()
    for job in jobs(media):
        if selected_modules is None or job[0] in selected_modules:
            tasks.put(job)
    deadline = time.monotonic()+int(setting('search_timeout','20'))
    def worker():
        while time.monotonic() < deadline and not cancel():
            try:
                name, fn = tasks.get_nowait()
            except queue.Empty:
                return
            try:
                out.put((name, fn() or [], ''))
            except Exception:
                out.put((name, [], 'provider failed'))
    with GUARD:
        ACTIVE = [threading.Thread(target=worker, daemon=True) for _ in range(2)]
        for t in ACTIVE:
            t.start()
    while any(t.is_alive() for t in ACTIVE) and time.monotonic() < deadline and not cancel():
        time.sleep(.1)
    items, errors = [], []
    while not out.empty():
        name, results, err = out.get_nowait()
        if err:
            errors.append(name + ': '+err)
        for result in results[:200]:
            s = normalize(result, name)
            if s:
                items.append(s)
    if any(t.is_alive() for t in ACTIVE):
        errors.append('Provider deadline reached; partial results only')
    return merge(items), errors
