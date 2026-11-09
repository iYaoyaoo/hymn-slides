# SQLite 索引 Schema（P1）

位置：缓存目录 `index.db`（便携模式为 `data/cache/index.db`）

## files —— 文件元数据

| 列 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | 主键 |
| path | TEXT NOT NULL UNIQUE | 绝对路径（str(Path)，平台分隔符） |
| rel_path | TEXT NOT NULL | 相对主目录路径 |
| name | TEXT NOT NULL | 文件名（含扩展名） |
| ext | TEXT NOT NULL | 扩展名（小写，如 .pptx） |
| size | INTEGER NOT NULL | 字节数 |
| mtime | REAL NOT NULL | 修改时间（Unix 秒，round 4 位） |
| page_count | INTEGER | 页数（P2 渲染后回填，可 NULL） |
| indexed_at | REAL NOT NULL | 入库时间 |

索引：`idx_files_name ON files(name)`；UNIQUE(path)

## slide_texts —— 幻灯片全文（P2 渲染时回填，P1 建表并支持搜索）

| 列 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | 主键 |
| file_id | INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE | 外键 |
| page | INTEGER NOT NULL | 页码（1 起） |
| text | TEXT NOT NULL | 该页提取文字 |

索引：`idx_texts_file ON slide_texts(file_id)`；`idx_texts_text ON slide_texts(text)`

外键：PRAGMA foreign_keys=ON（每次连接开启）

## 增量规则

- 文件存在且 `size` 与 `mtime` 均未变 → 跳过（不重写）
- 变化 → UPDATE（并清空该文件旧 slide_texts，待 P2 重新提取）
- 数据库中存在但磁盘已不存在 → DELETE（级联删 slide_texts）

## 支持扩展名

`.ppt .pptx .pps .ppsx .pot .potx .odp`（models.SUPPORTED_EXTS）

## 搜索（最简方案，LIKE 前后通配）

- 文件名：`name LIKE '%kw%'`（对 `%`/`_` 转义）
- 全文：`slide_texts.text LIKE '%kw%'`，返回 file+page+片段（关键词前后各 ~20 字符）
- v1 不引入 FTS5（素材规模小，LIKE 足够；留待性能不足时升级）
