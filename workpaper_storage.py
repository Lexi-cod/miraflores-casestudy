"""Saved-state encryption and retention for the single-household demonstration."""
import base64
import hashlib
import json
import os
from datetime import datetime, timezone

_cipher=None
secret=os.environ.get('WORKPAPER_ENCRYPTION_SECRET')
if secret:
    if len(secret)<32:raise RuntimeError('Use a generated encryption secret of at least 32 characters.')
    from cryptography.fernet import Fernet
    _cipher=Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))
elif os.environ.get('RENDER')=='true':
    raise RuntimeError('Render requires WORKPAPER_ENCRYPTION_SECRET. Use the supplied Blueprint.')

class RetiredRecord(ValueError):
    pass

class PostgresConnection:
    """Small DB-API adapter; the workpaper's transactional record is identical."""
    def __init__(self,url):
        import psycopg
        self.connection=psycopg.connect(url,connect_timeout=10,sslmode='require')

    def execute(self,sql,params=()):
        if sql in ['PRAGMA secure_delete=ON','VACUUM']:
            # PostgreSQL manages page reclamation. Provider backups have their own retention.
            return self.connection.execute('SELECT 1')
        if sql=='BEGIN IMMEDIATE':sql='SELECT pg_advisory_xact_lock(20251015)'
        if sql.startswith('INSERT OR IGNORE INTO workpaper'):
            sql=sql.replace('INSERT OR IGNORE','INSERT')+' ON CONFLICT (id) DO NOTHING'
        return self.connection.execute(sql.replace('?','%s'),params)

    def commit(self):self.connection.commit()
    def close(self):self.connection.close()
    def __enter__(self):return self
    def __exit__(self,kind,value,traceback):
        try:
            if kind:self.connection.rollback()
            else:self.connection.commit()
        finally:self.close()

def encode(state):
    raw=json.dumps(state,ensure_ascii=False,allow_nan=False)
    return 'encrypted:v1:'+_cipher.encrypt(raw.encode()).decode() if _cipher else raw

def decode(payload):
    if payload.startswith('encrypted:v1:'):
        if not _cipher:raise RuntimeError('The saved workpaper requires its original encryption secret.')
        payload=_cipher.decrypt(payload[len('encrypted:v1:'):].encode()).decode()
    return json.loads(payload)

def enforce_retention(c):
    """Erase only an expired saved case; a tombstone prevents silent re-creation."""
    c.execute('CREATE TABLE IF NOT EXISTS retention_tombstone (id INTEGER PRIMARY KEY CHECK(id=1), destroyed_at TEXT NOT NULL)')
    if c.execute('SELECT id FROM retention_tombstone WHERE id=1').fetchone():
        raise RetiredRecord('This saved engagement reached its retention deadline and was destroyed.')
    row=c.execute('SELECT payload FROM workpaper WHERE id=1').fetchone()
    if not row:return
    state=decode(row[0]);policy=state.get('retention',{})
    if policy.get('legal_hold') or not policy.get('expires_at'):return
    if datetime.fromisoformat(policy['expires_at'])>datetime.now(timezone.utc):return
    c.execute('PRAGMA secure_delete=ON')
    c.execute('DELETE FROM workpaper WHERE id=1')
    c.execute('INSERT INTO retention_tombstone VALUES (1,?)',(datetime.now(timezone.utc).isoformat(),))
    c.commit()
    c.execute('VACUUM')
    raise RetiredRecord('This saved engagement reached its retention deadline and was destroyed.')

def migrate_encryption(c):
    row=c.execute('SELECT payload FROM workpaper WHERE id=1').fetchone()
    if _cipher and row and not row[0].startswith('encrypted:v1:'):
        c.execute('PRAGMA secure_delete=ON')
        c.execute('UPDATE workpaper SET payload=? WHERE id=1',(encode(decode(row[0])),))
        c.commit();c.execute('VACUUM')
