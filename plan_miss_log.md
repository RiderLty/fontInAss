# Plan: 缺失日志系统重构 — 从文本迁移到 SQLite

## 1. 目标

将现有的纯文本 `miss_logs.txt` 重构为 SQLite 数据库，支持：
- 记录字幕请求 URL，关联缺失的字体/字形
- 按 URL、字体、字形多维度查询
- 聚合统计（热门缺失字体、问题最多的 URL）
- 关联分析（同一 URL 缺失哪些字体、同一字体出现在哪些 URL）
- 操作（删除单条url记录、清空全部）
- 大小限制自动淘汰

## 2. 数据库设计

### 2.1 五表星型模型

```
urls (维度表)                fonts (维度表)
┌──────────────────┐        ┌──────────────────┐
│ url        PK    │        │ font_name   PK   │
│ created_at       │        │ total_count      │
└──────────────────┘        │ last_seen        │
         │                  └──────────────────┘
         │ 1:N                       ▲
         ▼                           │
url_fonts (事实表)                   │
┌──────────────────┐        url_glyphs (事实表)
│ url_id      FK ──│──┐     ┌────────────────────┐
│ font_name   FK ──│──┼─┐   │ url_id        FK ──│──┐
│ count            │  │ │   │ font_name     FK ──│──┼─┐
│ first_seen       │  │ │   │ missing_chars      │  │ │
│ last_seen        │  │ │   │ count              │  │ │
└──────────────────┘  │ │   │ first_seen         │  │ │
                      │ │   │ last_seen          │  │ │
                      │ │   └────────────────────┘  │ │
                      │ │                           │ │
                      │ └──► fonts(font_name)       │ │
                      │                             │ │
                      └────────────────────────────►│ │
                                                    │ │
glyphs (维度表)                                      │ │
┌──────────────────────┐                             │ │
│ font_name      PK    │◄────────────────────────────┘ │
│ missing_chars  PK    │◄──────────────────────────────┘
│ total_count           │
│ last_seen             │
└──────────────────────┘
```

### 2.2 表结构 DDL

```sql
-- 维度表：URL
CREATE TABLE urls (
    url         TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL   -- ISO 8601
);

-- 维度表：字体
CREATE TABLE fonts (
    font_name   TEXT PRIMARY KEY,
    total_count INTEGER DEFAULT 0,  -- 全局累计出现次数
    last_seen   TEXT NOT NULL       -- 最近一次出现时间
);

-- 维度表：字形缺失
CREATE TABLE glyphs (
    font_name     TEXT NOT NULL,
    missing_chars TEXT NOT NULL,
    total_count   INTEGER DEFAULT 0,
    last_seen     TEXT NOT NULL,
    PRIMARY KEY (font_name, missing_chars)
);

-- 事实表：URL ↔ 字体缺失
CREATE TABLE url_fonts (
    url_id      TEXT NOT NULL REFERENCES urls(url)   ON DELETE CASCADE,
    font_name   TEXT NOT NULL REFERENCES fonts(font_name),
    count       INTEGER DEFAULT 1,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    PRIMARY KEY (url_id, font_name)
);

-- 事实表：URL ↔ 字形缺失
CREATE TABLE url_glyphs (
    url_id        TEXT NOT NULL REFERENCES urls(url)     ON DELETE CASCADE,
    font_name     TEXT NOT NULL,
    missing_chars TEXT NOT NULL,
    count         INTEGER DEFAULT 1,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    PRIMARY KEY (url_id, font_name, missing_chars),
    FOREIGN KEY (font_name, missing_chars) REFERENCES glyphs(font_name, missing_chars)
);
```

### 2.3 索引

```sql
-- 事实表查询索引
CREATE INDEX idx_uf_font ON url_fonts(font_name);
CREATE INDEX idx_uf_count ON url_fonts(count);
CREATE INDEX idx_uf_time ON url_fonts(last_seen);

CREATE INDEX idx_ug_url ON url_glyphs(url_id);
CREATE INDEX idx_ug_font ON url_glyphs(font_name);
CREATE INDEX idx_ug_count ON url_glyphs(count);
CREATE INDEX idx_ug_time ON url_glyphs(last_seen);

-- 维度表排序索引
CREATE INDEX idx_fonts_count ON fonts(total_count DESC);
CREATE INDEX idx_fonts_time ON fonts(last_seen DESC);
CREATE INDEX idx_glyphs_count ON glyphs(total_count DESC);
CREATE INDEX idx_glyphs_time ON glyphs(last_seen DESC);
```

### 2.4 大小限制与淘汰

- `MISS_LOGS_SIZE` 含义从"最大行数"改为"最大数据库文件大小 (MB)"
- 默认值 `20` （MB）
- 插入后用 `os.path.getsize()` 检查文件大小
- 超限时按 `urls.created_at` 升序删除最旧的 URL，CASCADE 自动清理关联记录
- 每次淘汰删一批（删到限制的 80%），避免频繁删除
- fonts/glyphs 维度表保留不删（本身很小，留着不影响大小且保留历史统计）

## 3. 后端改动

### 3.1 新建 `src/miss_logs_db.py` — 缺失日志数据库管理器

```python
class MissLogsDB:
    def __init__(self, db_path, max_size_kb):
        """初始化 SQLite 连接，建表建索引"""

    async def insert_font_miss(self, url, font_name):
        """记录字体缺失：upsert url/fonts/url_fonts，更新计数"""

    async def insert_glyph_miss(self, url, font_name, missing_chars):
        """记录字形缺失：upsert url/fonts/glyphs/url_glyphs，更新计数"""

    # === 查询方法 ===
    async def get_by_url(self, url):
        """某 URL 的全部缺失情况（字体+字形）"""

    async def get_font_detail(self, font_name):
        """某字体的全局统计 + 被哪些 URL 引用"""

    async def get_glyph_detail(self, font_name, missing_chars=None):
        """某字体的字形缺失详情"""

    async def get_all_fonts(self, sort_by='last_seen', order='desc'):
        """按字体查看全部缺失，支持排序"""

    async def get_all_urls(self, sort_by='last_seen', order='desc'):
        """按 URL 查看全部缺失，支持排序"""

    # === 聚合统计 ===
    async def get_summary(self):
        """总览：总字体数、总URL数、总字形数、总事件数"""

    async def get_top_fonts(self, limit=10):
        """Top N 缺失字体排行"""

    async def get_top_urls(self, limit=10):
        """Top N 问题最多的 URL 排行"""

    # === 关联分析 ===
    async def get_url_co_missing(self, url):
        """同一 URL 缺失的所有字体列表（共现分析）"""

    # === 操作 ===
    async def delete_url(self, url):
        """删除单个 URL 的所有记录"""

    async def delete_font(self, font_name):
        """删除单个字体的所有记录"""

    async def clear_all(self):
        """清空全部数据"""

    async def get_db_size(self):
        """返回当前数据库文件大小 (bytes)"""

    def _evict_if_needed(self):
        """超限时淘汰最旧的 URL"""
```

核心逻辑 — `insert_font_miss` 示例：
```python
async def insert_font_miss(self, url, font_name):
    now = datetime.now().isoformat()
    async with self._lock:
        # 1. Upsert url
        self._conn.execute(
            "INSERT INTO urls(url, created_at) VALUES(?, ?) "
            "ON CONFLICT(url) DO NOTHING", (url, now))
        # 2. Upsert font dimension
        self._conn.execute(
            "INSERT INTO fonts(font_name, total_count, last_seen) VALUES(?, 1, ?) "
            "ON CONFLICT(font_name) DO UPDATE SET "
            "total_count = total_count + 1, last_seen = ?", (font_name, now, now))
        # 3. Upsert url_font fact
        self._conn.execute(
            "INSERT INTO url_fonts(url_id, font_name, count, first_seen, last_seen) "
            "VALUES(?, ?, 1, ?, ?) "
            "ON CONFLICT(url_id, font_name) DO UPDATE SET "
            "count = count + 1, last_seen = ?", (url, font_name, now, now, now))
        self._conn.commit()
        self._evict_if_needed()
```

### 3.2 修改 `src/subsetter.py` — 错误处理与数据库写入

**改动点：**

1. **`load_subset_encode()`** — 返回结构化错误信息而非纯字符串：
   ```python
   # 当前:
   return f"字体缺失 \t\t[{font_name}]", ""
   # 改为:
   return {"type": "font", "font_name": font_name}, ""
   ```

2. **`font_subsetter()`** — 同样返回结构化信息：
   ```python
   # 当前:
   return f"缺少字形 \t\t[{font_name}]{miss_glyph}", result
   # 改为:
   return {"type": "glyph", "font_name": font_name, "chars": miss_glyph}, result
   ```

3. **`process()`** — 接收结构化错误，传入 URL，写入数据库：
   ```python
   async def process(self, raw_bytes, user_hsv_s, user_hsv_v, url=None):
       # ...existing code...
       for task in asyncio.as_completed(tasks):
           err, result = await task
           if err:
               total_errors.append(err)
               if isinstance(err, dict):
                   # 结构化错误 → 写数据库
                   if err["type"] == "font" and get_config("MISS_LOGS"):
                       if url:
                           asyncio.create_task(miss_logs_db.insert_font_miss(url, err["font_name"]))
                   elif err["type"] == "glyph" and get_config("MISS_GLYPH_LOGS"):
                       if url:
                           asyncio.create_task(miss_logs_db.insert_glyph_miss(url, err["font_name"], err["chars"]))
               # display_errors 仍用字符串
               # ...
   ```

4. **兼容性** — `total_errors` 列表中同时存结构化 dict 和字符串（异常情况），`"\n".join(total_errors)` 需要适配：
   ```python
   def _err_to_str(err):
       if isinstance(err, dict):
           if err["type"] == "font":
               return f"字体缺失 \t\t[{err['font_name']}]"
           else:
               return f"缺少字形 \t\t[{err['font_name']}]{err['chars']}"
       return str(err)
   ```

### 3.3 修改 `src/main.py` — 传递 URL + 新增 API 端点

**传递 URL：**

```python
# Proxy 模式（有 URL）
source_path = f"{request.url.path}?{request.url.query}"
error, srt, result_bytes = await process(raw_bytes, hsv_s, hsv_v, url=source_path)

# process_bytes 模式（无 URL，不记录）
error, srt, result_bytes = await process(raw_bytes, hsv_s, hsv_v)

# process_subset 模式（无 URL，不记录）
result = await process_subset(raw_bytes, ...)
```

**新增 API 端点：**

| 方法 | 路径 | 功能 |
|------|------|------|
| `GET` | `/api/miss-logs/summary` | 总览统计 |
| `GET` | `/api/miss-logs/fonts` | 按字体查看全部，支持 `?sort=last_seen&order=desc` |
| `GET` | `/api/miss-logs/fonts/{font_name}` | 某字体详情 + 关联 URL 列表 |
| `GET` | `/api/miss-logs/urls` | 按 URL 查看全部，支持排序 |
| `GET` | `/api/miss-logs/urls/{url_encoded}` | 某 URL 的缺失情况 |
| `GET` | `/api/miss-logs/glyphs?font={font_name}` | 某字体的字形缺失详情 |
| `GET` | `/api/miss-logs/top-fonts?limit=10` | Top N 缺失字体 |
| `GET` | `/api/miss-logs/top-urls?limit=10` | Top N 问题 URL |
| `DELETE` | `/api/miss-logs/urls/{url_encoded}` | 删除单个 URL 记录 |
| `DELETE` | `/api/miss-logs/fonts/{font_name}` | 删除单个字体记录 |
| `DELETE` | `/api/miss-logs/clear` | 清空全部 |

URL 编码方案：前端用 `encodeURIComponent(url)` 传递，后端 `urllib.parse.unquote` 解码。

### 3.4 修改 `src/constants.py`

```python
# 改动
MISS_LOGS_SIZE = int(os.environ.get("MISS_LOGS_SIZE", default=512))  # 从20改为512，单位从行数改为KB

# 移除（不再需要）
# MISS_LOGS_ORDER  # SQL ORDER BY 替代
# MISS_LOGS_NAME   # 固定为 miss_logs.db
```

### 3.5 修改 `src/config.py`

```python
"MISS_LOGS_SIZE": {
    "type": "integer",
    "default": 512,
    "min": 64,
    "max": 10240,
    "env_var": "MISS_LOGS_SIZE",
    "description": "缺失日志数据库最大大小 (KB)",
},
```

### 3.6 旧文件迁移

- 启动时检查 `logs/miss_logs.txt` 是否存在
- 如果存在，逐行解析并迁移到新数据库（无 URL，url 记为空字符串 `""`）
- 迁移完成后重命名为 `miss_logs.txt.bak`
- `src/logs.py` 的 `LogsManager` 保留不删（可能有其他用途），但 Subsetter 不再使用它

## 4. 前端改动

### 4.1 新建 `src/subset/src/composables/useMissLogs.js`

```javascript
export function useMissLogs() {
  const summary = ref({})
  const fonts = ref([])
  const urls = ref([])
  const fontDetail = ref(null)
  const urlDetail = ref(null)
  const glyphs = ref([])
  const topFonts = ref([])
  const topUrls = ref([])

  const fetchSummary = async () => { /* GET /api/miss-logs/summary */ }
  const fetchFonts = async (sort, order) => { /* GET /api/miss-logs/fonts */ }
  const fetchUrls = async (sort, order) => { /* GET /api/miss-logs/urls */ }
  const fetchFontDetail = async (fontName) => { /* GET /api/miss-logs/fonts/:name */ }
  const fetchUrlDetail = async (url) => { /* GET /api/miss-logs/urls/:url */ }
  const fetchGlyphs = async (fontName) => { /* GET /api/miss-logs/glyphs?font=:name */ }
  const fetchTopFonts = async (limit) => { /* GET /api/miss-logs/top-fonts */ }
  const fetchTopUrls = async (limit) => { /* GET /api/miss-logs/top-urls */ }
  const deleteUrl = async (url) => { /* DELETE /api/miss-logs/urls/:url */ }
  const deleteFont = async (fontName) => { /* DELETE /api/miss-logs/fonts/:name */ }
  const clearAll = async () => { /* DELETE /api/miss-logs/clear */ }

  return { summary, fonts, urls, fontDetail, urlDetail, glyphs,
           topFonts, topUrls, fetchSummary, fetchFonts, fetchUrls,
           fetchFontDetail, fetchUrlDetail, fetchGlyphs,
           fetchTopFonts, fetchTopUrls, deleteUrl, deleteFont, clearAll }
}
```

### 4.2 修改 `src/subset/src/views/DashboardView.vue`

在现有日志面板下方添加缺失日志区域：

```
┌─────────────────────────────────────────────────────┐
│ [状态卡片行: 版本 | 运行时间 | Python | 日志级别]      │
├─────────────────────────────────────────────────────┤
│ 实时日志                           [暂停] [清空]      │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 2026-04-28 10:00:01 INFO  字幕处理完成          │ │
│ │ ...                                             │ │
│ └─────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────┤
│ 缺失日志统计                     [清空全部]          │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐               │
│ │ 缺失  │ │ 影响  │ │ 字形  │ │ 事件  │               │
│ │ 字体  │ │ URL  │ │ 缺失  │ │ 总数  │               │
│ │  12   │ │  45  │ │  38  │ │ 156  │               │
│ └──────┘ └──────┘ └──────┘ └──────┘               │
│                                                     │
│ [按字体查看] [按URL查看] [Top字体] [Top URL]          │
│                                                     │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 表格: 字体名 | 缺失次数 | 最近出现 | 操作(删除)    │ │
│ │       Source Han Sans CN | 42 | 10:00 | [删除]   │ │
│ │       Noto Sans SC       | 18 | 09:55 | [删除]   │ │
│ │       ...                                        │ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ 点击字体名 → 展开详情面板:                            │
│ ┌─────────────────────────────────────────────────┐ │
│ │ Source Han Sans CN 详情                         │ │
│ │ 全局出现: 42次                                   │ │
│ │                                                 │ │
│ │ 关联URL:                                         │ │
│ │ /videos/123/Subtitles/1/Stream.ass  ×15         │ │
│ │ /videos/456/Subtitles/2/Stream.ass  ×12         │ │
│ │                                                 │ │
│ │ 字形缺失:                                        │ │
│ │ 缺失字符: 啊吧呢  (出现在 3 个URL)                │ │
│ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

**实现要点：**
- 统计卡片用 `a-row > a-col > a-card > a-statistic`
- 视图切换（按字体/按URL/Top）用 `a-segmented` 或 `a-radio-group`
- 数据表格用 `a-table`，支持列头点击排序
- 字体详情用展开行（`a-table` expandable）或侧边 `a-drawer`
- URL 过长时截断显示，hover 显示完整路径
- 无数据时显示提示："需要在设置中启用缺失日志记录"

### 4.3 修改 i18n 文件

**zh-CN.json 新增：**
```json
"missLogTitle": "缺失日志",
"missLogSummary": "统计概览",
"missLogTotalFonts": "缺失字体",
"missLogTotalUrls": "影响字幕",
"missLogTotalGlyphs": "字形缺失",
"missLogTotalEvents": "事件总数",
"missLogByFont": "按字体查看",
"missLogByUrl": "按URL查看",
"missLogTopFonts": "热门缺失字体",
"missLogTopUrls": "问题最多的字幕",
"missLogFontName": "字体名称",
"missLogMissingCount": "缺失次数",
"missLogLastSeen": "最近出现",
"missLogAction": "操作",
"missLogDelete": "删除",
"missLogClearAll": "清空全部",
"missLogUrl": "字幕地址",
"missLogMissingChars": "缺失字符",
"missLogReferencedUrls": "关联字幕",
"missLogGlyphDetail": "字形缺失详情",
"missLogNoData": "暂无缺失记录",
"missLogEnableHint": "需要在设置中启用缺失日志记录",
"missLogConfirmClear": "确认清空所有缺失日志？",
"missLogConfirmDelete": "确认删除此记录？"
```

**en-US.json 新增：**
```json
"missLogTitle": "Missing Logs",
"missLogSummary": "Summary",
"missLogTotalFonts": "Missing Fonts",
"missLogTotalUrls": "Affected URLs",
"missLogTotalGlyphs": "Glyph Missing",
"missLogTotalEvents": "Total Events",
"missLogByFont": "By Font",
"missLogByUrl": "By URL",
"missLogTopFonts": "Top Missing Fonts",
"missLogTopUrls": "Most Problematic URLs",
"missLogFontName": "Font Name",
"missLogMissingCount": "Count",
"missLogLastSeen": "Last Seen",
"missLogAction": "Action",
"missLogDelete": "Delete",
"missLogClearAll": "Clear All",
"missLogUrl": "Subtitle URL",
"missLogMissingChars": "Missing Characters",
"missLogReferencedUrls": "Referenced URLs",
"missLogGlyphDetail": "Glyph Details",
"missLogNoData": "No missing records",
"missLogEnableHint": "Enable missing log recording in Settings first",
"missLogConfirmClear": "Clear all missing logs?",
"missLogConfirmDelete": "Delete this record?"
```

## 5. 查询场景覆盖

| # | 场景 | API 端点 | SQL |
|---|------|----------|-----|
| 1 | 某 URL 缺了什么字体/字形 | `GET /api/miss-logs/urls/{url}` | `SELECT * FROM url_fonts WHERE url_id=?` + `SELECT * FROM url_glyphs WHERE url_id=?` |
| 2 | 某字体被哪些 URL 引用 | `GET /api/miss-logs/fonts/{name}` | `SELECT url, count, last_seen FROM url_fonts JOIN urls ON url_id=url WHERE font_name=?` |
| 3 | 某字体的全局计数 | `GET /api/miss-logs/fonts/{name}` | `SELECT * FROM fonts WHERE font_name=?` |
| 4 | 某字体的字形缺失 | `GET /api/miss-logs/glyphs?font={name}` | `SELECT * FROM url_glyphs WHERE font_name=? JOIN urls` |
| 5 | 按字体查看全部 | `GET /api/miss-logs/fonts?sort=last_seen` | `SELECT * FROM fonts ORDER BY last_seen DESC` |
| 6 | 按 URL 查看全部 | `GET /api/miss-logs/urls?sort=count` | `SELECT url, COUNT(*) ... GROUP BY url_id ORDER BY count DESC` |
| 7 | 按时间排序 | 上述端点 `?sort=last_seen` | `ORDER BY last_seen DESC` |
| 8 | 按次数排序 | 上述端点 `?sort=count` | `ORDER BY count DESC` |
| 9 | 总览统计 | `GET /api/miss-logs/summary` | 四个 COUNT 查询 |
| 10 | Top N 字体 | `GET /api/miss-logs/top-fonts?limit=10` | `SELECT * FROM fonts ORDER BY total_count DESC LIMIT ?` |
| 11 | Top N URL | `GET /api/miss-logs/top-urls?limit=10` | `SELECT url_id, SUM(count) ... GROUP BY url_id ORDER BY sum DESC LIMIT ?` |
| 12 | 同一 URL 缺失哪些字体 | `GET /api/miss-logs/urls/{url}` | 查询 url_fonts WHERE url_id=? |
| 13 | 删除单条 | `DELETE /api/miss-logs/urls/{url}` | `DELETE FROM urls WHERE url=?` (CASCADE) |
| 14 | 清空全部 | `DELETE /api/miss-logs/clear` | `DELETE FROM urls; DELETE FROM fonts; DELETE FROM glyphs` |
| 15 | 模糊搜索字体 | `GET /api/miss-logs/fonts?q=Source` | `SELECT * FROM fonts WHERE font_name LIKE '%Source%'` |

## 6. 实现顺序

| 阶段 | 内容 | 依赖 |
|------|------|------|
| 1 | 新建 `miss_logs_db.py`：建表、索引、CRUD 方法 | 无 |
| 2 | 修改 `subsetter.py`：返回结构化错误、传入 URL | 阶段 1 |
| 3 | 修改 `main.py`：传递 URL、新增 API 端点 | 阶段 1+2 |
| 4 | 修改 `constants.py` + `config.py`：配置项更新 | 无 |
| 5 | 旧文件迁移逻辑（启动时检查 txt → 迁移到 db） | 阶段 1 |
| 6 | 前端 `useMissLogs.js` composable | 阶段 3 |
| 7 | 前端 DashboardView.vue 添加缺失日志区域 | 阶段 6 |
| 8 | i18n 文件更新 | 阶段 7 |
| 9 | 构建测试 | 全部 |

## 7. 关键决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 数据库位置 | `data/miss_logs.db` | 独立于 fontmanager 的 db，避免耦合 |
| URL 来源 | proxy 模式的 `request.url.path` | batch/bytes 模式无 URL，不记录 |
| PK 类型 | TEXT（url/font_name） | 自然键，避免额外 ID 列 |
| 大小限制 | 文件大小 KB | 比行数更合理，URL 长短不一 |
| 维度表保留 | 淘汰时不删 fonts/glyphs | 本身很小，保留统计信息 |
| 旧文件处理 | 迁移后重命名为 .bak | 保留原始数据做备份 |
| SQL 方案 | 原生 sqlite3 | 项目已有 SQLAlchemy，但此场景简单，sqlite3 更轻量 |
