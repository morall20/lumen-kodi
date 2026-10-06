"""Build deterministic Kodi packages and feed; never embed account credentials."""
import hashlib
import json
import re
import shutil
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ADDONS = ('plugin.video.lumen', 'repository.lumen')


def source_files(folder):
    for path in sorted(folder.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            if path.is_symlink():
                raise ValueError('Symlinks are not permitted in a package')
            yield path.relative_to(folder).as_posix(), path.read_bytes()


def package(folder, destination):
    files = dict(source_files(folder))
    # Kodi only discovers higher version numbers. Published versions are immutable.
    if destination.exists():
        with zipfile.ZipFile(destination) as old:
            previous = {name.split('/', 1)[1]: old.read(name)
                        for name in old.namelist() if not name.endswith('/')}
        if previous != files:
            raise ValueError('Published package changed: increase version in ' + str(folder / 'addon.xml'))
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in files.items():
            info = zipfile.ZipInfo(folder.name + '/' + name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)


def build():
    feed = ROOT / 'repo'
    feed.mkdir(exist_ok=True)
    # Refresh the readable source inventory alongside each package.
    plugin = ROOT / 'plugin.video.lumen'
    manifest = {'version': ET.parse(plugin / 'addon.xml').getroot().get('version'),
                'target': 'Kodi 21.3 Omega',
                'status': 'development; live/device validation pending',
                'files': [{'path': name, 'sha256': hashlib.sha256(data).hexdigest()}
                          for name, data in source_files(plugin) if name != 'SOURCE_MANIFEST.json']}
    (plugin / 'SOURCE_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    index = ET.Element('addons')
    checksums = {}
    for addon_id in ADDONS:
        folder = ROOT / addon_id
        addon = ET.parse(folder / 'addon.xml').getroot()
        version = addon.get('version', '')
        if addon.get('id') != addon_id or not re.fullmatch(r'\d+\.\d+\.\d+', version):
            raise ValueError('Expected matching ID and numeric three-part version')
        index.append(addon)
        destination = feed / addon_id / (addon_id + '-' + version + '.zip')
        package(folder, destination)
        checksums[destination.relative_to(ROOT).as_posix()] = hashlib.sha256(destination.read_bytes()).hexdigest()
        (destination.with_suffix('.zip.sha256')).write_text(checksums[destination.relative_to(ROOT).as_posix()] + '\n')
        for asset in addon.findall('./extension/assets/*'):
            relative = Path(asset.text)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Invalid asset path')
            target = feed / addon_id / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(folder / relative, target)
        (feed / addon_id / 'addon.xml').write_bytes((folder / 'addon.xml').read_bytes())
    ET.indent(index, space='  ')
    data = ET.tostring(index, encoding='utf-8', xml_declaration=True) + b'\n'
    (feed / 'addons.xml').write_bytes(data)
    # This is Kodi's change marker, not a cryptographic authenticity signature.
    (feed / 'addons.xml.md5').write_text(hashlib.md5(data).hexdigest() + '\n')
    (feed / 'package-sha256.json').write_text(json.dumps(checksums, indent=2) + '\n')
    for path in feed.rglob('*.zip'):
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            assert all(not name.startswith('/') and '..' not in Path(name).parts for name in archive.namelist())
    print('Built Lumen packages and feed for ' + ', '.join(a.get('version') for a in index))


if __name__ == '__main__':
    build()
