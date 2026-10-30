from contextlib import closing
import os
import sqlite3
from test_engine import Environment
from decisionguard.operations import health, snapshot
from decisionguard.contracts import GuardError


class OperationsTests(Environment):
    def source(self):
        return self.db

    def test_backup_restore_disables_authority_and_preserves_receipts(self):
        source=self.source()
        self.engine.manage('review')
        self.engine.open_context('c','grant','memory')
        self.execute()
        self.engine.submit(self.action('pending'),principal='worker')
        with self.engine.store.transaction() as db:
            db.execute("INSERT INTO worker_runs VALUES('r','c','digest','running','{}')")
        before=self.engine.inspect()['receipt_count']
        backup=self.root/'backup.sqlite3'; restored=self.root/'restored.sqlite3'
        snapshot(source,backup)
        self.assertTrue(health(backup)['recovery_review_required'])
        snapshot(backup,restored,restore=True)
        self.assertFalse(health(restored)['recovery_review_required'])
        with closing(sqlite3.connect(restored)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM grants WHERE revoked=0').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM receipts').fetchone()[0],before)
            self.assertEqual(db.execute("SELECT status FROM actions WHERE request_id='pending'").fetchone()[0],'cancelled')
            self.assertEqual(db.execute('SELECT count(*) FROM contexts WHERE quarantined=0').fetchone()[0],0)
            self.assertEqual(db.execute("SELECT count(*) FROM events WHERE kind='restore_locked'").fetchone()[0],1)
        self.assertEqual(restored.stat().st_mode & 0o777,0o600)

    def test_never_overwrites_or_creates_missing_source(self):
        target=self.root/'existing';target.write_text('keep')
        with self.assertRaises(FileExistsError): snapshot(self.source(),target)
        self.assertEqual(target.read_text(),'keep')
        missing=self.root/'missing'
        with self.assertRaises(GuardError): health(missing)
        self.assertFalse(missing.exists())

    def test_invalid_schema_cleans_partial_backup(self):
        source=self.source()
        with closing(sqlite3.connect(source)) as db: db.execute('PRAGMA user_version=999')
        dest=self.root/'bad'
        with self.assertRaises(GuardError): snapshot(source,dest)
        self.assertFalse(dest.exists())

    def test_rejects_public_or_symlink_source(self):
        source=self.source(); link=self.root/'link';link.symlink_to(source)
        with self.assertRaises(GuardError): health(link)
        os.chmod(source,0o644)
        with self.assertRaises(GuardError): snapshot(source,self.root/'bad')

    def test_backup_includes_committed_wal_and_leaves_source_authority(self):
        with closing(sqlite3.connect(self.db)) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute('PRAGMA wal_autocheckpoint=0')
            self.execute()
            dest=self.root/'wal-backup'
            snapshot(self.db,dest)
            with closing(sqlite3.connect(dest)) as backup:
                self.assertEqual(backup.execute('SELECT count(*) FROM receipts').fetchone()[0],1)
            self.assertEqual(writer.execute('SELECT revoked FROM grants').fetchone()[0],0)
