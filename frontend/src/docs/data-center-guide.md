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
| **strm_tasks** | 虚拟链接 (STRM) 生成任务记录 |
| **health_check_configs** | 系统健康检查监控配置 |
| **users** | 系统用户账户与认证信息 |
| **task_records** | 任务中心执行记录（整理/STRM/RSS等任务的日志） |
| **system_logs** | 系统操作审计日志 |
| **feeds** | RSS 订阅源地址与连接配置 |
| **feed_items** | RSS 抓取到的下载条目记录 |

### metadata Schema
存放 100w+ 级别的全球元数据资产。

| 表名 | 说明 |
|------|------|
| **tmdb_deep_meta** | TMDB 深度元数据（海报、剧情、演员等） |
| **media_title_index** | 媒体标题加速索引（用于快速匹配 ID） |
| **ref_genres** | 番剧类型字典 |
| **ref_companies** | 动画制作/发行公司资料 |
| **ref_keywords** | 番剧特征关键词库 |
| **bgm_archive** | Bangumi 归档数据 |
| **recognition_corrections** | 用户手动指定的识别修正映射 |
| **user_genre_mapping** | 用户自定义流派 ID 中文映射 |
| **user_company_mapping** | 用户自定义公司 ID 中文映射 |
| **user_keyword_mapping** | 用户自定义关键词 ID 中文映射 |
| **user_language_mapping** | 用户自定义语言代码中文映射 |
| **user_country_mapping** | 用户自定义国家代码中文映射 |

#### 核心表：tmdb_deep_meta (超级表)

**表结构：**
```sql
CREATE TABLE metadata.tmdb_deep_meta (
    tmdb_id VARCHAR,          -- TMDB ID
    media_type VARCHAR,         -- movie / tv
    title VARCHAR,             -- 官方最新标题
    custom_title VARCHAR,       -- [永久固定标题] 用户修正后固化
    original_title VARCHAR,      -- 原始标题
    origin_country VARCHAR,      -- 制作国家
    original_language VARCHAR,   -- 原始语言
    first_air_date VARCHAR,     -- 首播日期
    last_air_date VARCHAR,      -- 最后更新日期
    
    poster_path VARCHAR,        -- 海报路径
    overview TEXT,             -- 剧情简介
    
    genre_ids VARCHAR,         -- 流派 ID 列表 (逗号分隔)
    company_ids VARCHAR,        -- 制作公司 ID 列表
    keyword_ids VARCHAR,        -- 关键词 ID 列表
    
    alias_pool JSONB,          -- 别名池
    title_pool JSONB,          -- 标题池
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
| `genre_ids` | VARCHAR | 流派 ID：逗号分隔的字符串，如 "16,10749" |
| `company_ids` | VARCHAR | 制作公司 ID：用于二级分类规则匹配 |
| `keyword_ids` | VARCHAR | 关键词 ID：用于标题匹配增强 |

#### 索引表：media_title_index

**用途：** 支持毫秒级标题匹配和模糊搜索

```sql
CREATE TABLE metadata.media_title_index (
    id SERIAL PRIMARY KEY,
    title VARCHAR,              -- 标题 (支持 pg_trgm 模糊匹配)
    year VARCHAR,               -- 年份
    tmdb_id VARCHAR,           -- 关联 TMDB ID
    media_type VARCHAR,          -- 媒体类型
    source VARCHAR,              -- 数据来源 (tmdb, sytmdb, user)
    
    INDEX (title),              -- 精确匹配索引
    INDEX (year),
    INDEX (tmdb_id),
    INDEX (media_type)
);
```

**匹配策略：**
1. **精确匹配**：优先尝试完全匹配标题和年份
2. **模糊匹配**：使用 `pg_trgm` 的 `%` 操作符进行相似度搜索
3. **评分算法**：多重结果时，动漫优先权重 + 相似度排序

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
1. 精确匹配 (media_title_index)
  ↓ (失败)
2. 模糊匹配 (pg_trgm % 操作符)
  ↓
3. 多重结果评分算法
  - 动漫优先权重 (+100)
  - 相似度排序
  - 年份匹配验证
  ↓
4. 返回最佳匹配结果
```

**性能优化：**
- 使用联合查询减少数据库往返
- 限制候选数量防止性能抖动
- 支持动漫优先模式

### 2. TmdbFullClassifier - 二级分类处理器

**职责：** 根据元数据特征计算二级分类路径

**支持的匹配规则：**
- `genre_ids`: 流派匹配 (如 "16" 代表动漫)
- `company_ids`: 制作公司匹配
- `keyword_ids`: 关键词匹配
- `origin_country`: 制作国家匹配
- `original_language`: 原始语言匹配

**智能字段提取：**
- 自动兼容新旧字段名 (如 `genre_ids` vs `genres`)
- 从 `full_data` JSONB 中提取中文国家名
- 支持列表和字符串两种格式

**示例规则：**
```json
{
  "name": "动漫",
  "target": "all",
  "enabled": true,
  "criteria": {
    "genre_ids": "16",
    "origin_country": "JP"
  }
}
```

### 3. TmdbFullIngestor - 数据抓取入库

**职责：** 从 TMDB API 抓取数据并存入本地数据库

**智能更新策略：**
- 检测空壳记录：只存在 ID 但无流派信息的记录
- 避免重复抓取：流派信息完整时跳过
- 保留用户修正：`custom_title` 和 `is_custom` 字段永不覆盖

### 4. TmdbFullBrowser - 数据浏览导出

**职责：** 提供数据浏览、搜索和导出功能

**功能：**
- 分页浏览：支持分页查询元数据
- 全量导出：导出为字典格式
- 模糊搜索：基于标题的快速搜索

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
1. 首次入库: title="天穗之咲稻姬", custom_title=null
2. 用户修正: custom_title="天穗之咲稻姬 (2024)", is_custom=true
3. TMDB 更新: title="Sakuna: Rice and Ruin", custom_title 保持不变 ✅
```

### 场景 3：二级分类

**自动计算分类路径：**
```
元数据: {
  "genre_ids": "16,10749",
  "origin_country": "JP",
  "company_ids": "141300"
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
1. 在"数据中心浏览"中确认该条目的资料是否已固化
2. 检查 `genre_ids`、`company_ids` 等字段是否有值
3. 验证规则的 `criteria` 配置是否正确

### 3. 性能优化

- 确保 PostgreSQL 已启用 `pg_trgm` 扩展
- 定期清理 `media_title_index` 中的重复记录
- 监控数据库连接池使用情况
