import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release',ROOT/'scripts/build_release.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)

class ReleaseTests(unittest.TestCase):
    def test_reproducible_archive_and_member_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'a.zip';b=Path(tmp)/'b.zip'
            self.assertEqual(release.build(a),release.build(b))
            self.assertEqual(a.read_bytes(),b.read_bytes())
            with zipfile.ZipFile(a) as z:
                sums=json.loads(z.read('decisionguard-v1/SHA256SUMS.json'))
                for name,expected in sums.items():
                    self.assertEqual(hashlib.sha256(z.read('decisionguard-v1/'+name)).hexdigest(),expected)
                self.assertIn('LICENSE',sums)
                self.assertIn('src/decisionguard/web/app.js',sums)
            with self.assertRaises(FileExistsError): release.build(a)
