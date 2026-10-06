import tempfile
from pathlib import Path
import unittest
import zipfile
from build_repository import package, source_files


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'plugin.video.example'
        self.folder.mkdir()
        (self.folder / 'addon.xml').write_text('<addon id="plugin.video.example" version="1.0.0"/>')
        (self.folder / 'default.py').write_text('print("example")\n')
        self.destination = self.root / 'package.zip'

    def test_deterministic_single_root_archive(self):
        package(self.folder, self.destination)
        first = self.destination.read_bytes()
        self.destination.unlink()
        package(self.folder, self.destination)
        self.assertEqual(first, self.destination.read_bytes())
        with zipfile.ZipFile(self.destination) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), {'plugin.video.example/addon.xml', 'plugin.video.example/default.py'})

    def test_published_version_cannot_be_replaced(self):
        package(self.folder, self.destination)
        original = self.destination.read_bytes()
        (self.folder / 'default.py').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'increase version'):
            package(self.folder, self.destination)
        self.assertEqual(original, self.destination.read_bytes())

    def test_generated_bytecode_excluded(self):
        cache = self.folder / '__pycache__'
        cache.mkdir()
        (cache / 'cached.pyc').write_bytes(b'not-source')
        (self.folder / 'stale.pyc').write_bytes(b'not-source')
        self.assertEqual({p for p, _ in source_files(self.folder)}, {'addon.xml', 'default.py'})

    def test_symlink_rejected(self):
        (self.folder / 'outside.py').symlink_to(self.folder / 'default.py')
        with self.assertRaisesRegex(ValueError, 'Symlinks'):
            package(self.folder, self.destination)


if __name__ == '__main__':
    unittest.main()
