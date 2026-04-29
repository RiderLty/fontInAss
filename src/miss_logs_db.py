import asyncio
import os
import sqlite3
from datetime import datetime

from constants import logger


class MissLogsDB:
    def __init__(self, db_path, max_size_mb=20):
        self._db_path = db_path
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._lock = asyncio.Lock()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT,
                created_at  TEXT NOT NULL,
                hash        TEXT
            );

            CREATE TABLE IF NOT EXISTS miss_fonts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id  INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
                font_name   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS miss_glyphs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id   INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
                font_name    TEXT NOT NULL,
                missing_chars TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_req_url ON requests(url);
            CREATE INDEX IF NOT EXISTS idx_req_created ON requests(created_at);
            CREATE INDEX IF NOT EXISTS idx_mf_request ON miss_fonts(request_id);
            CREATE INDEX IF NOT EXISTS idx_mf_font ON miss_fonts(font_name);
            CREATE INDEX IF NOT EXISTS idx_mg_request ON miss_glyphs(request_id);
            CREATE INDEX IF NOT EXISTS idx_mg_font ON miss_glyphs(font_name);
            CREATE INDEX IF NOT EXISTS idx_mg_chars ON miss_glyphs(font_name, missing_chars);
        """)
        self._conn.commit()

    # ========== 写入 ==========

    async def insert_request(self, record: dict):
        now = datetime.now().isoformat()
        async with self._lock:
            cur = self._conn.execute(
                "INSERT INTO requests(url, created_at, hash) VALUES(?, ?, ?)",
                (record.get("url"), now, record.get("hash")))
            request_id = cur.lastrowid

            for font_name in record.get("miss_fonts", []):
                self._conn.execute(
                    "INSERT INTO miss_fonts(request_id, font_name) VALUES(?, ?)",
                    (request_id, font_name))

            for g in record.get("miss_glyphs", []):
                self._conn.execute(
                    "INSERT INTO miss_glyphs(request_id, font_name, missing_chars) VALUES(?, ?, ?)",
                    (request_id, g["font_name"], g["missing_chars"]))

            self._conn.commit()
            self._evict_if_needed()

    # ========== 查询 ==========

    async def get_summary(self):
        async with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM requests")
            total_requests = cur.fetchone()[0]
            cur = self._conn.execute("SELECT COUNT(DISTINCT url) FROM requests WHERE url IS NOT NULL")
            total_urls = cur.fetchone()[0]
            cur = self._conn.execute("SELECT COUNT(DISTINCT font_name) FROM miss_fonts")
            total_fonts = cur.fetchone()[0]
            cur = self._conn.execute("SELECT COUNT(*) FROM (SELECT DISTINCT font_name, missing_chars FROM miss_glyphs)")
            total_glyphs = cur.fetchone()[0]
        return {
            "total_requests": total_requests,
            "total_urls": total_urls,
            "total_fonts": total_fonts,
            "total_glyphs": total_glyphs,
        }

    async def get_fonts(self, sort_by='total_count', order='desc', q=None):
        allowed_sorts = {'font_name', 'total_count', 'last_seen'}
        if sort_by not in allowed_sorts:
            sort_by = 'total_count'
        order_dir = 'ASC' if order == 'asc' else 'DESC'
        sql = (
            "SELECT mf.font_name, COUNT(*) as total_count, MAX(r.created_at) as last_seen "
            "FROM miss_fonts mf JOIN requests r ON mf.request_id = r.id"
        )
        params = []
        if q:
            sql += " WHERE mf.font_name LIKE ?"
            params.append(f"%{q}%")
        sql += f" GROUP BY mf.font_name ORDER BY {sort_by} {order_dir}"
        async with self._lock:
            cur = self._conn.execute(sql, params)
            return [{"font_name": r[0], "total_count": r[1], "last_seen": r[2]}
                    for r in cur.fetchall()]

    async def get_urls(self, sort_by='last_seen', order='desc'):
        allowed_sorts = {'url', 'request_count', 'last_seen'}
        if sort_by not in allowed_sorts:
            sort_by = 'last_seen'
        order_dir = 'ASC' if order == 'asc' else 'DESC'
        sql = (
            "SELECT url, COUNT(*) as request_count, MAX(created_at) as last_seen "
            "FROM requests WHERE url IS NOT NULL GROUP BY url "
            f"ORDER BY {sort_by} {order_dir}"
        )
        async with self._lock:
            cur = self._conn.execute(sql)
            return [{"url": r[0], "request_count": r[1], "last_seen": r[2]}
                    for r in cur.fetchall()]

    async def get_glyphs(self, sort_by='total_count', order='desc', font_name=None):
        allowed_sorts = {'font_name', 'missing_chars', 'total_count', 'last_seen'}
        if sort_by not in allowed_sorts:
            sort_by = 'total_count'
        order_dir = 'ASC' if order == 'asc' else 'DESC'
        sql = (
            "SELECT mg.font_name, mg.missing_chars, COUNT(*) as total_count, "
            "MAX(r.created_at) as last_seen "
            "FROM miss_glyphs mg JOIN requests r ON mg.request_id = r.id"
        )
        params = []
        if font_name:
            sql += " WHERE mg.font_name LIKE ?"
            params.append(f"%{font_name}%")
        sql += f" GROUP BY mg.font_name, mg.missing_chars ORDER BY {sort_by} {order_dir}"
        async with self._lock:
            cur = self._conn.execute(sql, params)
            return [{"font_name": r[0], "missing_chars": r[1], "total_count": r[2],
                     "last_seen": r[3]} for r in cur.fetchall()]

    async def get_font_detail(self, font_name):
        async with self._lock:
            cur = self._conn.execute(
                "SELECT COUNT(*), MAX(r.created_at) "
                "FROM miss_fonts mf JOIN requests r ON mf.request_id = r.id "
                "WHERE mf.font_name = ?",
                (font_name,))
            row = cur.fetchone()
            if not row or row[0] == 0:
                return None
            total_count = row[0]
            last_seen = row[1]

            cur = self._conn.execute(
                "SELECT r.url, COUNT(*) as cnt, MAX(r.created_at) as last "
                "FROM miss_fonts mf JOIN requests r ON mf.request_id = r.id "
                "WHERE mf.font_name = ? AND r.url IS NOT NULL "
                "GROUP BY r.url ORDER BY cnt DESC",
                (font_name,))
            urls = [{"url": r[0], "count": r[1], "last_seen": r[2]} for r in cur.fetchall()]

        return {
            "font_name": font_name,
            "total_count": total_count,
            "last_seen": last_seen,
            "urls": urls,
        }

    async def get_glyph_font_detail(self, font_name):
        async with self._lock:
            cur = self._conn.execute(
                "SELECT COUNT(*), MAX(r.created_at) "
                "FROM miss_glyphs mg JOIN requests r ON mg.request_id = r.id "
                "WHERE mg.font_name = ?",
                (font_name,))
            row = cur.fetchone()
            if not row or row[0] == 0:
                return None
            total_count = row[0]
            last_seen = row[1]

            cur = self._conn.execute(
                "SELECT r.url, COUNT(*) as cnt, MAX(r.created_at) as last "
                "FROM miss_glyphs mg JOIN requests r ON mg.request_id = r.id "
                "WHERE mg.font_name = ? AND r.url IS NOT NULL "
                "GROUP BY r.url ORDER BY cnt DESC",
                (font_name,))
            urls = [{"url": r[0], "count": r[1], "last_seen": r[2]} for r in cur.fetchall()]

            cur = self._conn.execute(
                "SELECT missing_chars, COUNT(*) as cnt, MAX(r.created_at) as last "
                "FROM miss_glyphs mg JOIN requests r ON mg.request_id = r.id "
                "WHERE mg.font_name = ? "
                "GROUP BY missing_chars ORDER BY cnt DESC",
                (font_name,))
            glyphs = [{"missing_chars": r[0], "total_count": r[1], "last_seen": r[2]}
                      for r in cur.fetchall()]

        return {
            "font_name": font_name,
            "total_count": total_count,
            "last_seen": last_seen,
            "urls": urls,
            "glyphs": glyphs,
        }

    async def get_url_detail(self, url):
        async with self._lock:
            cur = self._conn.execute(
                "SELECT COUNT(*), MAX(created_at) FROM requests WHERE url = ?",
                (url,))
            row = cur.fetchone()
            if not row or row[0] == 0:
                return None
            request_count = row[0]
            last_seen = row[1]

            cur = self._conn.execute(
                "SELECT mf.font_name, COUNT(*) as cnt "
                "FROM miss_fonts mf JOIN requests r ON mf.request_id = r.id "
                "WHERE r.url = ? GROUP BY mf.font_name ORDER BY cnt DESC",
                (url,))
            fonts = [{"font_name": r[0], "count": r[1]} for r in cur.fetchall()]

            cur = self._conn.execute(
                "SELECT mg.font_name, mg.missing_chars, COUNT(*) as cnt "
                "FROM miss_glyphs mg JOIN requests r ON mg.request_id = r.id "
                "WHERE r.url = ? GROUP BY mg.font_name, mg.missing_chars ORDER BY cnt DESC",
                (url,))
            glyphs = [{"font_name": r[0], "missing_chars": r[1], "count": r[2]}
                      for r in cur.fetchall()]

        return {
            "url": url,
            "request_count": request_count,
            "last_seen": last_seen,
            "fonts": fonts,
            "glyphs": glyphs,
        }

    # ========== 操作 ==========

    async def delete_url(self, url):
        async with self._lock:
            self._conn.execute("DELETE FROM requests WHERE url = ?", (url,))
            self._conn.commit()

    async def clear_all(self):
        async with self._lock:
            self._conn.execute("DELETE FROM miss_glyphs")
            self._conn.execute("DELETE FROM miss_fonts")
            self._conn.execute("DELETE FROM requests")
            self._conn.commit()

    async def get_db_size(self):
        return os.path.getsize(self._db_path) if os.path.exists(self._db_path) else 0

    def _evict_if_needed(self):
        try:
            size = os.path.getsize(self._db_path)
        except OSError:
            return
        if size <= self._max_size_bytes:
            return
        target = int(self._max_size_bytes * 0.8)
        cur = self._conn.execute("SELECT id FROM requests ORDER BY created_at ASC")
        ids = [r[0] for r in cur.fetchall()]
        for rid in ids:
            self._conn.execute("DELETE FROM requests WHERE id = ?", (rid,))
            try:
                if os.path.getsize(self._db_path) <= target:
                    break
            except OSError:
                break
        self._conn.commit()

    def close(self):
        self._conn.close()
