### 高性能 PostgreSQL 数据中心架构

系统采用"单库双 Schema"架构，实现业务数据与海量元数据的完美隔离，支持毫秒级离线识别。

> **架构优势：离线优先 + 数据主权**
>
> 基于 PostgreSQL 的 `pg_trgm` 插件实现毫秒级模糊匹配，并引入 **"超级表"** 机制，确保您的手动修正永远优先且受保护。即使 TMDB API 不可用，系统依然可以正常工作。

---

## 数据库架构

### public Schema
存放系统核心业务数据。

| 表名 | 说明 |
|------|------|
| **subscriptions** | 番剧追剧任务配置 |
| **subscribed_episodes** | 已执行下载的剧集记录（防重） |
| **organize_history** | 文件整理重命名的历史记录 |
| **series_fingerprint** | 智能记忆（用于加速识别和去重） |
| **filter_rules** | RSS 包含/排除等过滤规则 |
| **rules** | 识别引擎正则与自定义规则 |
| **secondary_rules** | 自动分类与分库逻辑配置 |
| **download_history** | 下载器的任务执行历史 |
| **blacklist** | 识别排除黑名单关键词 |
| **subscription_templates** | 订阅预设模板 |
| **discover_cache** | 系统发现页（趋势/热门/搜索）的临时数据缓存 |
| **remote_rules** | 从远程 URL 同步下来的社区识别与清理规则 |
| **calendar_subjects** | 番剧放送时刻表数据 |
| **quality_profiles** | 下载质量优先偏好设置 |
| **health_check_configs** | 系统健康检查监控配置 |
| **users** | 系统用户账户与认证信息 |
| **sessions** | 登录会话管理（Token、设备、过期时间） |
| **task_records** | 任务中心执行记录（整理/STRM/RSS等任务的日志） |
| **system_logs** | 系统操作审计日志 |
| **feeds** | RSS 订阅源地址与连接配置 |
| **feed_items** | RSS 抓取到的下载条目记录 |
| **file_hashes** | 文件哈希记录（SHA1/ED2K，整理时按 ED2K 去重写入，用于历史追溯） |
| **rss_detect_tasks** | RSS 探测订阅任务（按 URL 定时探测并自动订阅） |
| **bangumi_data_item** | Bangumi 数据条目（Bangumi ID 到 TMDB/MAL/AniList/AniDB 的映射，含完整原始数据） |
| **bangumi_raw_cache** | Bangumi 原始 API 响应缓存（完结番剧的 Subject/Episodes/Characters 原始响应，永久缓存） |
| **bgm_user_mark** | Bangumi 用户手动标记（季度番剧表"已整理"等） |
| **tmdb_blocklist** | TMDB 主动屏蔽列表 |
| **emby_media_index** | Emby 库索引（媒体库定时同步） |
| **rapid_upload_retry** | CD2 秒传重试队列：秒传未命中的文件按间隔自动重试（整理管理-秒传管理） |
| **cd2_dir_cache** | CD2 目录锁定快照缓存：锁定的目录浏览/扫描/生成走本地快照（0 API），解锁即删除 |
| **custom_scheduled_jobs** | 自定义定时任务（任务计划页创建的 cron/间隔任务） |
| **notification_records** | 通知中心发送记录（Telegram 等渠道的消息渲染留档） |
| **webhook_events** | 联动记录中心（Webhook 事件台账：CD2 联动成败、重试记录，并引用 task_records 保存全链路日志） |
| **chat_sessions** | AI 助手对话会话（消息历史与上下文快照，清空后聊天记录不可恢复） |
| **skill_enabled_state** | AI 技能启用/禁用开关状态 |
| **font_subset_history** | 字体子集化处理历史（整理任务随行字幕的字体抽条记录） |
| **font_subtitle_jobs** | 字体管家任务队列（字幕检查/子集化任务的执行状态） |

### metadata Schema
存放 100w+ 级别的全球元数据资产。

| 表名 | 说明 |
|------|------|
| **tmdb_deep_meta** | TMDB 深度元数据（海报、剧情、演员等） |
| **media_title_index** | 媒体标题加速索引（用于快速匹配 ID） |
| **ref_genres** | 番剧类型字典 |
| **ref_companies** | 动画制作/发行公司资料 |
| **ref_keywords** | 番剧特征关键词库 |
| **user_genre_mapping** | 用户自定义流派 ID 中文映射 |
| **user_company_mapping** | 用户自定义公司 ID 中文映射 |
| **user_keyword_mapping** | 用户自定义关键词 ID 中文映射 |
| **user_language_mapping** | 用户自定义语言代码中文映射 |
| **user_country_mapping** | 用户自定义国家代码中文映射 |

> **关于用户修正**：系统不再使用独立的 `recognition_corrections` 表。手动修正直接固化在 `tmdb_deep_meta` 表的 `custom_title` 和 `is_custom` 字段中，确保修正永远优先且受保护（详见下方"用户修正保护"章节）。

#### 核心表：tmdb_deep_meta (超级表)

**表结构：**
```sql
CREATE TABLE metadata.tmdb_deep_meta (
    tmdb_id VARCHAR,          -- TMDB ID
    media_type VARCHAR,         -- movie / tv
    title VARCHAR,             -- 官方最新标题
    custom_title VARCHAR,       -- [永久固定标题] 用户修正后固化
    original_title VARCHAR,      -- 原始标题
    origin_country VARCHAR[],    -- 制作国家代码数组 (如 {JP,CN})
    original_language VARCHAR,   -- 原始语言
    first_air_date VARCHAR,     -- 首播/上映日期
    last_air_date VARCHAR,      -- 最后更新日期（剧集）

    poster_path VARCHAR,        -- 海报路径
    overview TEXT,             -- 剧情简介

    genre_ids INTEGER[],        -- 流派 ID 数组 (如 {16,10749})
    company_ids INTEGER[],      -- 制作公司 ID 数组
    keyword_ids INTEGER[],      -- 关键词 ID 数组

    alias_pool JSONB,          -- 别名池（alternative_titles 原始列表）
    title_pool JSONB,          -- 标题池（全部标题去重列表）
    full_data JSONB,           -- TMDB 完整档案 (JSONB)
    is_custom BOOLEAN,          -- 用户修正保护标记
    updated_at TIMESTAMP,        -- 更新时间

    PRIMARY KEY (tmdb_id, media_type)
);
```

**核心字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `custom_title` | VARCHAR | **永久固定标题**：首次入库时自动固化，后续全量更新不会被覆盖 |
| `title` | VARCHAR | 官方最新标题：TMDB 的当前标题，用于参考对比 |
| `is_custom` | BOOLEAN | 用户修正保护：手动修改或从 SYTMDB 同步后进入保护状态 |
| `full_data` | JSONB | 完整档案：存储 TMDB 的演职员、评分、高清海报等全部数据 |
| `poster_path` | VARCHAR | 海报路径：用于前端展示和 Telegram 通知 |
| `overview` | TEXT | 剧情简介：支持离线查看 |
| `genre_ids` | INTEGER[] | 流派 ID：整数数组，如 `{16,10749}`，用于二级分类规则匹配 |
| `company_ids` | INTEGER[] | 制作公司 ID：整数数组，用于二级分类规则匹配 |
| `keyword_ids` | INTEGER[] | 关键词 ID：整数数组，用于标题匹配增强 |
| `origin_country` | VARCHAR[] | 制作国家代码数组：同时作为二级分类"原始国家"条件的匹配对象 |

#### 索引表：media_title_index

**用途：** 支持毫秒级标题匹配和模糊搜索

```sql
CREATE TABLE metadata.media_title_index (
    id SERIAL PRIMARY KEY,
    title VARCHAR,              -- 标题 (支持 pg_trgm 模糊匹配)
    year VARCHAR,               -- 年份
    tmdb_id VARCHAR,           -- 关联 TMDB ID
    media_type VARCHAR,          -- 媒体类型
    source VARCHAR              -- 数据来源 (primary / original / translation / alias)
);
CREATE INDEX ON metadata.media_title_index (title);
CREATE INDEX ON metadata.media_title_index (year);
CREATE INDEX ON metadata.media_title_index (tmdb_id);
CREATE INDEX ON metadata.media_title_index (media_type);
```

**匹配策略：**
1. **精确匹配**：优先尝试完全匹配标题（可叠加年份、媒体类型条件）
2. **模糊匹配**：使用 `pg_trgm` 的 `%` 操作符进行相似度搜索，按 `similarity()` 从高到低排序，限制候选 10 条
3. **评分算法**：多重结果时，动漫优先权重 + 来源可靠度权重（见 TmdbFullMatcher）

#### 参考表：标准化标签库

| 表名 | 说明 |
|------|------|
| `ref_genres` | 流派参考库 (id, name_zh, name_en) |
| `ref_companies` | 制作公司参考库 (id, name, country) |
| `ref_keywords` | 关键词参考库 (id, name_en) |

#### 用户映射表：自定义标签

| 表名 | 说明 |
|------|------|
| `user_genre_mapping` | 用户自定义流派映射 |
| `user_company_mapping` | 用户自定义公司映射 |
| `user_keyword_mapping` | 用户自定义关键词映射 |
| `user_language_mapping` | 语言代码映射 |
| `user_country_mapping` | 国家代码映射 |

---

## 核心功能模块

### 1. TmdbFullMatcher - 离线识别引擎

**职责：** 本地离线识别与标题匹配

**工作流程：**
```
输入: 标题 + 年份 + 类型
  ↓
1. 精确匹配 (media_title_index，可叠加年份/类型条件)
  ↓ (失败)
2. 模糊匹配 (pg_trgm % 操作符，按 similarity() 降序，限候选 10 条)
  ↓
3. 多重结果评分算法
  - 动漫优先权重：流派含 16（动画）+100
  - 日漫加权：原始语言为 ja 再 +50
  - 来源可靠度：primary(30) > original(25) > translation(20) > alias(10)
  ↓
4. 按最佳候选回 tmdb_deep_meta 主表补全深层字段
  （标题取 custom_title > title，固定名优先）
  ↓
5. 返回标准识别结果（source 标记为 offline_cache）
```

**性能优化：**
- 索引表与主表联合查询，减少数据库往返
- 模糊匹配限制候选数量防止性能抖动
- 支持动漫优先模式

### 2. TmdbFullClassifier - 二级分类处理器

**职责：** 根据元数据特征计算二级分类路径。同一套特征构建口径（`build_features`）也被 TMDB 屏蔽条目的"档案条件"复用，两边判定语义完全一致。

**支持的匹配规则（criteria）：** 字段之间为 **与** 关系（填写的字段须全部满足才命中）；未填写的字段不参与判定。除 `year`/`title` 外，值支持逗号分隔多个，**命中任一即算满足**。

| 字段 | 界面名称 | 匹配对象 | 判定方式 |
|------|---------|---------|---------|
| `genre_ids` | 流派 | 作品流派 ID | 条件值与作品流派 ID 集合**有交集**即命中（如 "16" 代表动漫） |
| `company_ids` | 制作公司 | 制作公司 ID | 同上，集合交集 |
| `keyword_ids` | 关键词 | 关键词 ID | 同上，集合交集 |
| `origin_country` | 原始国家 | 国家/地区 | 集合交集；作品国家集合同时含代码（JP、CN）与 `full_data` 里的中文国家名（日本），两种写法都可作为条件值 |
| `original_language` | 原始语言 | 原始语言代码 | **精确匹配**（如 ja、en），多值逗号分隔命中任一 |
| `year` | 年份/范围 | 开播/上映年份 | 单值（`2024`）须精确相等；区间（`2020-2024`）按闭区间包含判断 |
| `title` | 名称匹配 | 档案标题 | 多个关键词逗号分隔，**任一关键词以子串形式**出现在标题中即命中（忽略大小写）。标题取值优先级：`custom_title` > `title` > `name` |

**智能字段提取：**
- 自动兼容新旧字段名 (如 `genre_ids` vs `genres`)
- 年份取 `first_air_date` / `release_date` 前 4 位
- 从 `full_data` JSONB 中提取中文国家名并入国家集合
- 支持列表和字符串两种格式

**示例规则：**
```json
{
  "name": "动漫",
  "target": "all",
  "enabled": true,
  "criteria": {
    "genre_ids": "16",
    "origin_country": "JP",
    "year": "2020-2026",
    "title": "LIVE,演唱会"
  }
}
```
上例含义：流派含动漫 **且** 国家为日本 **且** 年份在 2020-2026 间 **且** 标题带 "LIVE" 或 "演唱会"（忽略大小写）的作品才命中。

### 3. TmdbFullIngestor - 数据抓取入库

**职责：** 从 TMDB API 抓取数据、格式化脱水后原子化写入数据库

**抓取：** 请求 `/3/{movie|tv}/{id}`，`language=zh-CN`，`append_to_response=alternative_titles,keywords,translations,credits`，支持按代理设置走代理。

**脱水入库（save_to_db）：**
- **华语优先**：标题/简介按 简中(CN) > 新加坡(SG) > 香港(HK) > 台湾(TW) > 默认 > 原始 的优先级挑选；原产地为中国大陆且原始语言为中文时直接用原始名称（通常是简体中文）
- **永久名称锁定**：库中已有 `custom_title` 则继承不覆盖；没有则以本次标题固化。`is_custom` 默认开启锁定
- **索引表重建**：`media_title_index` 按该 ID 先清空再批量插入，标题按来源分级 primary（主标题）/ original（原名）/ translation（翻译）/ alias（别名）
- **参考表维护**：`ref_genres` / `ref_companies` / `ref_keywords` 以 ON CONFLICT DO UPDATE 批量 Upsert

**智能更新策略（TmdbMateFullManager.fetch_and_ingest）：**
- 检测空壳记录：只存在 ID 但无流派信息的记录，自动激活全量同步
- 避免重复抓取：记录存在且流派信息完整时跳过
- 保留用户修正：`custom_title` 和 `is_custom` 字段永不覆盖

### 4. TmdbFullBrowser - 数据浏览导出

**职责：** 提供数据浏览、搜索和导出功能

**功能：**
- 分页浏览：按 `updated_at` 倒序分页查询元数据
- 全字段搜索：标题 / 原始标题 / 固定标题 / TMDB ID / 原始语言 模糊匹配，并反查流派、公司、关键词参考表（搜"动画"能命中流派含动画的条目）
- 名称解析：浏览结果中的流派/公司/关键词 ID 自动解析为中文名称，`custom_title` 存在时以固定标题展示并标记 manual
- 字典导出：导出流派 / 公司 / 关键词全量字典，以及库内已有的语言与国家列表（供二级分类规则填写条件值参考）

### 5. BangumiRawCache - 完结番剧原始响应缓存

**职责：** 对 Bangumi 三个核心 API 端点统一管理永久缓存，减少对官方 API 的重复请求。

**触发条件：** 番剧在 `bangumi_data_item.end` 字段记录的完结时间超过当前时间 30 天以上时，视为"长完结"，其原始 API 响应视为稳定数据，永久缓存到本地。

**覆盖的 API 端点：**

| 端点 | 统一入口 | raw_cache 列 |
|------|---------|--------------|
| `GET /v0/subjects/{id}` | `_fetch_subject_raw` | `subject_data` |
| `GET /v0/episodes` | `_fetch_episodes_raw` | `episodes_data` |
| `GET /v0/subjects/{id}/characters` | `_fetch_characters_raw` | `characters_data` |

**两层缓存策略：**

```
请求进入
  ↓
① discover_cache (上层应用缓存，7天，加工后数据，所有番剧统一生效)
  ├─ 命中 → 返回
  └─ 未命中 ↓
② bangumi_raw_cache (原始响应永久缓存，仅完结番剧)
    ├─ is_long_ended? (查 bangumi_data_item.end)
    │   ├─ 是 → 查 raw_cache
    │   │       ├─ 命中 → 返回（不再请求 API）
    │   │       └─ 未命中 → 请求官方 API → 写入 raw_cache → 返回
    │   └─ 否 → 请求官方 API → 返回
    ↓
加工数据 → 写 discover_cache → 返回
```

**关键特性：**
- **单一入口**：全项目所有对这三个端点的请求都收口到三个统一入口，业务代码无需关心完结状态
- **判断内聚**：`is_long_ended` 判断只在统一入口内部出现，调用方完全无感
- **写入隔离**：`bangumi_raw_cache` 的写入只在统一入口里发生，不会散落到各业务方法

---

## 使用场景

### 场景 1：离线识别

**无需 TMDB API，本地秒级匹配：**
```
文件名: "[ANi] 天穗之咲稻姬 S01E02"
  ↓
TmdbFullMatcher.resolve()
  ↓
返回: {
  "id": 255492,
  "title": "天穗之咲稻姬",
  "type": "tv",
  "category": "剧集",
  "source": "offline_cache"
}
```

### 场景 2：用户修正保护

**手动修正标题后永久生效：**
```
1. 首次入库: title="天穗之咲稻姬", custom_title="天穗之咲稻姬"（首见即固化）
2. 用户修正: custom_title="天穗之咲稻姬 (2024)", is_custom=true
3. TMDB 更新: title="Sakuna: Rice and Ruin", custom_title 保持不变 ✅
```

### 场景 3：二级分类

**自动计算分类路径：**
```
元数据: {
  "genre_ids": [16, 10749],
  "origin_country": ["JP"],
  "company_ids": [141300]
}
  ↓
TmdbFullClassifier.calculate()
  ↓
匹配规则: "动漫" (genre=16, country=JP)
  ↓
返回: "动漫/日本/TV东京"
```

---

## 维护建议

### 1. 定期全量更新

建议每月执行一次全量数据更新，确保元数据时效性：
- 系统会自动检测空壳记录并补充完整信息
- 保留所有用户修正，不会覆盖 `custom_title`

### 2. 规则验证

如果发现二级分类规则未生效：
1. 在数据中心页面的「元数据资产」标签中搜索该条目，确认资料是否已固化入库
2. 检查 `genre_ids`、`company_ids` 等字段是否有值
3. 验证规则的 `criteria` 配置是否正确

### 3. 性能优化

- 确保 PostgreSQL 已启用 `pg_trgm` 扩展
- 定期清理 `media_title_index` 中的重复记录
- 监控数据库连接池使用情况
