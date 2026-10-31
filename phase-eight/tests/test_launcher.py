import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from test_engine import ROOT
from decisionguard.launcher import main
from decisionguard.storage import Store

class LauncherTests(TestCase):
    def test_start_creates_empty_store_and_opens_ui_without_overwriting(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/'state.sqlite3'
            with patch('decisionguard.launcher.serve') as serve:
                self.assertEqual(main(['--db',str(db)]),0)
                serve.assert_called_once_with(db,8765,open_browser=True)
            before=db.read_bytes()
            with patch('decisionguard.launcher.serve'):
                self.assertEqual(main(['--db',str(db),'--no-browser']),0)
            self.assertEqual(db.read_bytes(),before)
            with Store(db).transaction() as sql:
                self.assertEqual(sql.execute('SELECT count(*) FROM resources').fetchone()[0],0)
