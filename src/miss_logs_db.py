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
            CREATE TABLE IF NOT EXISTS urls (
                url         TEXT PRIMARY KEY,
                created_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fonts (
                font_name   TEXT PRIMARY KEY,
                total_count INTEGER DEFAULT 0,
                last_seen   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS glyphs (
                font_name     TEXT NOT NULL,
                missing_chars TEXT NOT NULL,
                total_count   INTEGER DEFAULT 0,
                last_seen     TEXT NOT NULL,
                PRIMARY KEY (font_name, missing_chars)
            );
            CREATE TABLE IF NOT EXISTS url_fonts (
                url_id      TEXT NOT NULL REFERENCES urls(url) ON DELETE CASCADE,
                font_name   TEXT NOT NULL REFERENCES fonts(font_name),
                count       INTEGER DEFAULT 1,
                first_seen  TEXT NOT NULL,
                last_seen   TEXT NOT NULL,
                PRIMARY KEY (url_id, font_name)
            );
            CREATE TABLE IF NOT EXISTS url_glyphs (
                url_id        TEXT NOT NULL REFERENCES urls(url) ON DELETE CASCADE,
                font_name     TEXT NOT NULL,
                missing_chars TEXT NOT NULL,
                count         INTEGER DEFAULT 1,
                first_seen    TEXT NOT NULL,
                last_seen     TEXT NOT NULL,
                PRIMARY KEY (url_id, font_name, missing_chars),
                FOREIGN KEY (font_name, missing_chars) REFERENCES glyphs(font_name, missing_chars)
            );

            CREATE INDEX IF NOT EXISTS idx_uf_font ON url_fonts(font_name);
            CREATE INDEX IF NOT EXISTS idx_uf_count ON url_fonts(count);
            CREATE INDEX IF NOT EXISTS idx_uf_time ON url_fonts(last_seen);
            CREATE INDEX IF NOT EXISTS idx_ug_url ON url_glyphs(url_id);
            CREATE INDEX IF NOT EXISTS idx_ug_font ON url_glyphs(font_name);
            CREATE INDEX IF NOT EXISTS idx_ug_count ON url_glyphs(count);
            CREATE INDEX IF NOT EXISTS idx_ug_time ON url_glyphs(last_seen);
            CREATE INDEX IF NOT EXISTS idx_fonts_count ON fonts(total_count DESC);
            CREATE INDEX IF NOT EXISTS idx_fonts_time ON fonts(last_seen DESC);
            CREATE INDEX IF NOT EXISTS idx_glyphs_count ON glyphs(total_count DESC);
            CREATE INDEX IF NOT EXISTS idx_glyphs_time ON glyphs(last_seen DESC);
        """)
        self._conn.commit()

    # ========== 写入 ==========

    async def insert_font_miss(self, url, font_name):
        now = datetime.now().isoformat()
        async with self._lock:
            self._conn.execute(
                "INSERT INTO urls(url, created_at) VALUES(?, ?) "
                "ON CONFLICT(url) DO NOTHING", (url, now))
            self._conn.execute(
                "INSERT INTO fonts(font_name, total_count, last_seen) VALUES(?, 1, ?) "
                "ON CONFLICT(font_name) DO UPDATE SET "
                "total_count = total_count + 1, last_seen = excluded.last_seen",
                (font_name, now))
            self._conn.execute(
                "INSERT INTO url_fonts(url_id, font_name, count, first_seen, last_seen) "
                "VALUES(?, ?, 1, ?, ?) "
                "ON CONFLICT(url_id, font_name) DO UPDATE SET "
                "count = count + 1, last_seen = excluded.last_seen",
                (url, font_name, now, now))
            self._conn.commit()
            self._evict_if_needed()

    async def insert_glyph_miss(self, url, font_name, missing_chars):
        now = datetime.now().isoformat()
        async with self._lock:
            self._conn.execute(
                "INSERT INTO urls(url, created_at) VALUES(?, ?) "
                "ON CONFLICT(url) DO NOTHING", (url, now))
            self._conn.execute(
                "INSERT INTO fonts(font_name, total_count, last_seen) VALUES(?, 1, ?) "
                "ON CONFLICT(font_name) DO UPDATE SET "
                "total_count = total_count + 1, last_seen = excluded.last_seen",
                (font_name, now))
            self._conn.execute(
                "INSERT INTO glyphs(font_name, missing_chars, total_count, last_seen) "
                "VALUES(?, ?, 1, ?) "
                "ON CONFLICT(font_name, missing_chars) DO UPDATE SET "
                "total_count = total_count + 1, last_seen = excluded.last_seen",
                (font_name, missing_chars, now))
            self._conn.execute(
                "INSERT INTO url_fonts(url_id, font_name, count, first_seen, last_seen) "
                "VALUES(?, ?, 1, ?, ?) "
                "ON CONFLICT(url_id, font_name) DO UPDATE SET "
                "count = count + 1, last_seen = excluded.last_seen",
                (url, font_name, now, now))
            self._conn.execute(
                "INSERT INTO url_glyphs(url_id, font_name, missing_chars, count, first_seen, last_seen) "
                "VALUES(?, ?, ?, 1, ?, ?) "
                "ON CONFLICT(url_id, font_name, missing_chars) DO UPDATE SET "
                "count = count + 1, last_seen = excluded.last_seen",
                (url, font_name, missing_chars, now, now))
            self._conn.commit()
            self._evict_if_needed()

    # ========== 查询 ==========

    async def get_summary(self):
        async with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM fonts")
            total_fonts = cur.fetchone()[0]
            cur = self._conn.execute("SELECT COUNT(*) FROM urls")
            total_urls = cur.fetchone()[0]
            cur = self._conn.execute("SELECT COUNT(*) FROM glyphs")
            total_glyphs = cur.fetchone()[0]
            cur = self._conn.execute("SELECT COALESCE(SUM(count), 0) FROM url_fonts")
            total_events = cur.fetchone()[0]
        return {
            "total_fonts": total_fonts,
            "total_urls": total_urls,
            "total_glyphs": total_glyphs,
            "total_events": total_events,
        }

    async def get_all_fonts(self, sort_by='last_seen', order='desc', q=None):
        allowed_sorts = {'font_name', 'total_count', 'last_seen'}
        if sort_by not in allowed_sorts:
            sort_by = 'last_seen'
        order_dir = 'ASC' if order == 'asc' else 'DESC'
        sql = f"SELECT font_name, total_count, last_seen FROM fonts"
        params = []
        if q:
            sql += " WHERE font_name LIKE ?"
            params.append(f"%{q}%")
        sql += f" ORDER BY {sort_by} {order_dir}"
        async with self._lock:
            cur = self._conn.execute(sql, params)
            return [{"font_name": r[0], "total_count": r[1], "last_seen": r[2]}
                    for r in cur.fetchall()]

    async def get_all_urls(self, sort_by='last_seen', order='desc'):
        allowed_sorts = {'url', 'font_count', 'last_seen'}
        order_dir = 'ASC' if order == 'asc' else 'DESC'
        if sort_by == 'font_count':
            sql = (f"SELECT u.url, u.created_at, COUNT(uf.font_name) as font_count, "
                   f"MAX(uf.last_seen) as last_seen "
                   f"FROM urls u LEFT JOIN url_fonts uf ON u.url = uf.url_id "
                   f"GROUP BY u.url ORDER BY font_count {order_dir}")
        elif sort_by == 'url':
            sql = f"SELECT url, created_at, 0, created_at FROM urls ORDER BY url {order_dir}"
        else:
            sql = (f"SELECT u.url, u.created_at, COUNT(uf.font_name) as font_count, "
                   f"MAX(uf.last_seen) as last_seen "
                   f"FROM urls u LEFT JOIN url_fonts uf ON u.url = uf.url_id "
                   f"GROUP BY u.url ORDER BY last_seen {order_dir}")
        async with self._lock:
            cur = self._conn.execute(sql)
            return [{"url": r[0], "created_at": r[1], "font_count": r[2], "last_seen": r[3]}
                    for r in cur.fetchall()]

    async def get_font_detail(self, font_name):
        async with self._lock:
            cur = self._conn.execute(
                "SELECT font_name, total_count, last_seen FROM fonts WHERE font_name = ?",
                (font_name,))
            row = cur.fetchone()
            if not row:
                return None
            cur = self._conn.execute(
                "SELECT uf.url_id, uf.count, uf.last_seen "
                "FROM url_fonts uf WHERE uf.font_name = ? ORDER BY uf.count DESC",
                (font_name,))
            urls = [{"url": r[0], "count": r[1], "last_seen": r[2]} for r in cur.fetchall()]
            cur = self._conn.execute(
                "SELECT missing_chars, total_count, last_seen FROM glyphs WHERE font_name = ? "
                "ORDER BY total_count DESC", (font_name,))
            glyphs = [{"missing_chars": r[0], "total_count": r[1], "last_seen": r[2]}
                      for r in cur.fetchall()]
        return {
            "font_name": row[0],
            "total_count": row[1],
            "last_seen": row[2],
            "urls": urls,
            "glyphs": glyphs,
        }

    async def get_url_detail(self, url):
        async with self._lock:
            cur = self._conn.execute(
                "SELECT url, created_at FROM urls WHERE url = ?", (url,))
            row = cur.fetchone()
            if not row:
                return None
            cur = self._conn.execute(
                "SELECT uf.font_name, uf.count, uf.last_seen "
                "FROM url_fonts uf WHERE uf.url_id = ? ORDER BY uf.count DESC",
                (url,))
            fonts = [{"font_name": r[0], "count": r[1], "last_seen": r[2]} for r in cur.fetchall()]
            cur = self._conn.execute(
                "SELECT ug.font_name, ug.missing_chars, ug.count, ug.last_seen "
                "FROM url_glyphs ug WHERE ug.url_id = ? ORDER BY ug.count DESC",
                (url,))
            glyphs = [{"font_name": r[0], "missing_chars": r[1], "count": r[2], "last_seen": r[3]}
                      for r in cur.fetchall()]
        return {
            "url": row[0],
            "created_at": row[1],
            "fonts": fonts,
            "glyphs": glyphs,
        }

    async def get_glyphs_by_font(self, font_name):
        async with self._lock:
            cur = self._conn.execute(
                "SELECT g.font_name, g.missing_chars, g.total_count, g.last_seen "
                "FROM glyphs g WHERE g.font_name = ? ORDER BY g.total_count DESC",
                (font_name,))
            rows = cur.fetchall()
            result = []
            for r in rows:
                cur2 = self._conn.execute(
                    "SELECT url_id, count, last_seen FROM url_glyphs "
                    "WHERE font_name = ? AND missing_chars = ? ORDER BY count DESC",
                    (r[0], r[1]))
                urls = [{"url": x[0], "count": x[1], "last_seen": x[2]} for x in cur2.fetchall()]
                result.append({
                    "font_name": r[0], "missing_chars": r[1],
                    "total_count": r[2], "last_seen": r[3], "urls": urls,
                })
        return result

    async def get_all_glyphs(self, sort_by='total_count', order='desc', font_name=None):
        allowed_sorts = {'font_name', 'missing_chars', 'total_count', 'last_seen'}
        if sort_by not in allowed_sorts:
            sort_by = 'total_count'
        order_dir = 'ASC' if order == 'asc' else 'DESC'
        sql = "SELECT font_name, missing_chars, total_count, last_seen FROM glyphs"
        params = []
        if font_name:
            sql += " WHERE font_name LIKE ?"
            params.append(f"%{font_name}%")
        sql += f" ORDER BY {sort_by} {order_dir}"
        async with self._lock:
            cur = self._conn.execute(sql, params)
            return [{"font_name": r[0], "missing_chars": r[1], "total_count": r[2], "last_seen": r[3]}
                    for r in cur.fetchall()]

    async def get_top_fonts(self, limit=10):
        async with self._lock:
            cur = self._conn.execute(
                "SELECT font_name, total_count, last_seen FROM fonts "
                "ORDER BY total_count DESC LIMIT ?", (limit,))
            return [{"font_name": r[0], "total_count": r[1], "last_seen": r[2]}
                    for r in cur.fetchall()]

    async def get_top_urls(self, limit=10):
        async with self._lock:
            cur = self._conn.execute(
                "SELECT url_id, SUM(count) as total, MAX(last_seen) "
                "FROM url_fonts GROUP BY url_id ORDER BY total DESC LIMIT ?", (limit,))
            return [{"url": r[0], "total_count": r[1], "last_seen": r[2]}
                    for r in cur.fetchall()]

    async def get_url_co_missing(self, url):
        async with self._lock:
            cur = self._conn.execute(
                "SELECT font_name, count, last_seen FROM url_fonts "
                "WHERE url_id = ? ORDER BY count DESC", (url,))
            return [{"font_name": r[0], "count": r[1], "last_seen": r[2]}
                    for r in cur.fetchall()]

    # ========== 操作 ==========

    async def delete_url(self, url):
        async with self._lock:
            self._conn.execute("DELETE FROM urls WHERE url = ?", (url,))
            self._conn.commit()

    async def clear_all(self):
        async with self._lock:
            self._conn.execute("DELETE FROM url_glyphs")
            self._conn.execute("DELETE FROM url_fonts")
            self._conn.execute("DELETE FROM urls")
            self._conn.execute("DELETE FROM fonts")
            self._conn.execute("DELETE FROM glyphs")
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
        cur = self._conn.execute("SELECT url FROM urls ORDER BY created_at ASC")
        urls = [r[0] for r in cur.fetchall()]
        for url in urls:
            self._conn.execute("DELETE FROM urls WHERE url = ?", (url,))
            try:
                if os.path.getsize(self._db_path) <= target:
                    break
            except OSError:
                break
        self._conn.commit()

    # ========== 迁移旧文件 ==========

    def migrate_from_txt(self, txt_path):
        if not os.path.exists(txt_path):
            return 0
        lines = []
        with open(txt_path, 'r', encoding='utf-8') as f:
            for line in f:
                key = line.strip()
                if key:
                    lines.append(key)
        if not lines:
            return 0
        now = datetime.now().isoformat()
        for line in lines:
            if line.startswith("字体缺失"):
                font_name = self._parse_font_name(line)
                if font_name:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO urls(url, created_at) VALUES('', ?)", (now,))
                    self._conn.execute(
                        "INSERT INTO fonts(font_name, total_count, last_seen) VALUES(?, 1, ?) "
                        "ON CONFLICT(font_name) DO UPDATE SET "
                        "total_count = total_count + 1, last_seen = excluded.last_seen",
                        (font_name, now))
                    self._conn.execute(
                        "INSERT INTO url_fonts(url_id, font_name, count, first_seen, last_seen) "
                        "VALUES('', ?, 1, ?, ?) "
                        "ON CONFLICT(url_id, font_name) DO UPDATE SET "
                        "count = count + 1, last_seen = excluded.last_seen",
                        (font_name, now, now))
            elif line.startswith("缺少字形"):
                font_name, chars = self._parse_glyph_info(line)
                if font_name:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO urls(url, created_at) VALUES('', ?)", (now,))
                    self._conn.execute(
                        "INSERT INTO fonts(font_name, total_count, last_seen) VALUES(?, 1, ?) "
                        "ON CONFLICT(font_name) DO UPDATE SET "
                        "total_count = total_count + 1, last_seen = excluded.last_seen",
                        (font_name, now))
                    self._conn.execute(
                        "INSERT INTO glyphs(font_name, missing_chars, total_count, last_seen) "
                        "VALUES(?, ?, 1, ?) "
                        "ON CONFLICT(font_name, missing_chars) DO UPDATE SET "
                        "total_count = total_count + 1, last_seen = excluded.last_seen",
                        (font_name, chars, now))
                    self._conn.execute(
                        "INSERT INTO url_fonts(url_id, font_name, count, first_seen, last_seen) "
                        "VALUES('', ?, 1, ?, ?) "
                        "ON CONFLICT(url_id, font_name) DO UPDATE SET "
                        "count = count + 1, last_seen = excluded.last_seen",
                        (font_name, now, now))
                    self._conn.execute(
                        "INSERT INTO url_glyphs(url_id, font_name, missing_chars, count, first_seen, last_seen) "
                        "VALUES('', ?, ?, 1, ?, ?) "
                        "ON CONFLICT(url_id, font_name, missing_chars) DO UPDATE SET "
                        "count = count + 1, last_seen = excluded.last_seen",
                        (font_name, chars, now, now))
        self._conn.commit()
        return len(lines)

    @staticmethod
    def _parse_font_name(line):
        import re
        m = re.search(r'\[([^\]]+)\]', line)
        return m.group(1).strip() if m else None

    @staticmethod
    def _parse_glyph_info(line):
        import re
        m = re.search(r'\[([^\]]+)\](.*)', line)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return None, ""

    def close(self):
        self._conn.close()
