"""Bounded radar tables in Kodi's existing local lumen.db; cross-process lease."""
import json
import time
import uuid
from contextlib import closing, contextmanager
from runtime import db


@contextmanager
def connection():
    with closing(db()) as c, c:
        c.execute('CREATE TABLE IF NOT EXISTS radar_release (key TEXT PRIMARY KEY, first_seen REAL NOT NULL, published REAL NOT NULL, updated REAL NOT NULL, data TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS radar_metadata (key TEXT PRIMARY KEY, updated REAL NOT NULL, data TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS radar_control (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        yield c


def get(key, default=None):
    with connection() as c:
        row = c.execute('SELECT value FROM radar_control WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default


def put(key, value):
    with connection() as c:
        c.execute('INSERT OR REPLACE INTO radar_control VALUES (?,?)', (key,json.dumps(value)))


def acquire(interval, force=False, now=None):
    now = time.time() if now is None else now
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        rows = dict(c.execute("SELECT key,value FROM radar_control WHERE key IN ('lease','attempt')"))
        lease = json.loads(rows.get('lease','{}'))
        last = json.loads(rows.get('attempt','0'))
        if lease.get('until',0)>now or now-last < (60 if force else interval):
            return None
        token = uuid.uuid4().hex
        c.execute('INSERT OR REPLACE INTO radar_control VALUES (?,?)', ('lease',json.dumps({'token':token,'until':now+180})))
        c.execute('INSERT OR REPLACE INTO radar_control VALUES (?,?)', ('attempt',json.dumps(now)))
        return token


def release(token):
    with connection() as c:
        row = c.execute("SELECT value FROM radar_control WHERE key='lease'").fetchone()
        if row and json.loads(row[0]).get('token')==token:
            c.execute("DELETE FROM radar_control WHERE key='lease'")


def save(key, record, now=None):
    now = time.time() if now is None else now
    with connection() as c:
        previous = c.execute('SELECT first_seen FROM radar_release WHERE key=?',(key,)).fetchone()
        record = dict(record, first_seen=previous[0] if previous else now)
        c.execute('INSERT OR REPLACE INTO radar_release VALUES (?,?,?,?,?)',
                  (key,record['first_seen'],record.get('published',0),now,json.dumps(record)))
        c.execute('DELETE FROM radar_release WHERE key NOT IN (SELECT key FROM radar_release ORDER BY updated DESC LIMIT 2000)')


def records():
    with connection() as c:
        return [json.loads(row[0]) for row in c.execute('SELECT data FROM radar_release ORDER BY CASE WHEN published>0 THEN published ELSE first_seen END DESC, first_seen DESC LIMIT 2000')]


def metadata(key):
    with connection() as c:
        row = c.execute('SELECT updated,data FROM radar_metadata WHERE key=?',(key,)).fetchone()
        return (row[0],json.loads(row[1])) if row else (0,None)


def save_metadata(key, data):
    with connection() as c:
        c.execute('INSERT OR REPLACE INTO radar_metadata VALUES (?,?,?)',(key,time.time(),json.dumps(data)))
        c.execute('DELETE FROM radar_metadata WHERE key NOT IN (SELECT key FROM radar_metadata ORDER BY updated DESC LIMIT 2000)')


def clear():
    with connection() as c:
        row = c.execute("SELECT value FROM radar_control WHERE key='lease'").fetchone()
        if row and json.loads(row[0]).get('until',0)>time.time():
            return False
        for table in ('radar_release','radar_metadata','radar_control'):
            c.execute('DELETE FROM '+table)
    return True
