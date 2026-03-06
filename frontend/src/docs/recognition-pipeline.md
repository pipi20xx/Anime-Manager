# 全链路识别流水线架构详解 (ANIME Pro Matcher Pipeline)

本文档详细拆解了系统的核心识别引擎架构。该引擎采用高度解耦的分层设计（Layered Architecture），确保了核心算法的纯粹性与数据源的可扩展性。

---

## 🏗️ 核心架构分层概览

系统自上而下分为四层，每一层遵循严格的职责边界：

| 逻辑层级 | 物理路径 (Backend) | 性质 | 核心职能与设计哲学 |
| :--- | :--- | :--- | :--- |
| **API 接口层** | `routers/recognition.py` | **接入** | **(Entry)** 仅负责接收 HTTP 请求与参数校验，不做任何业务处理，直接唤醒 L3 编排器。 |
| **L3 编排层** | `recognition/pipeline/` | **胶水** | **(Orchestrator)** 业务的大脑。定义识别的"步骤"与"顺序"。它负责指挥 L1 进行解析，指挥 L2 获取数据，并管理全局上下文 (`Context`) 的状态流转。 |
| **L2 数据层** | `recognition/data_provider/` | **I/O** | **(Data Provider)** 系统的手脚。负责一切与"外部"的交互（TMDB API, Bangumi API, 数据库, 文件系统）。**只提供原始数据，不负责判断数据是否匹配。** |
| **L1 内核层** | `recognition_engine/` | **纯逻辑** | **(Kernel)** 系统的核心算法。**纯 CPU 计算，无 I/O，无副作用。** 负责字符串清洗、正则提取、Anitopy 封装、以及最关键的"对撞算法"（计算两个标题是否属于同一部番剧）。 |

---

## 🌊 深度全链路数据流转图 (Deep Dive Data Flow)

结合实际运行日志的完整生命周期解析（包含**智能记忆命中**与**特权提取**分支）：

```text
[用户请求] (文件名: "[LoliHouse] Spy x Family - 13 [1080p].mkv")
    ⬇️
[API 层] (routers/recognition.py)
    ⬇️ 1. 启动工作流
[L3 编排层] (recognition/recognizer.py) -> 实例化 Context (状态容器)
    │
    ├── ⚡ [Step 0: 智能记忆预检] (Fingerprint Check)
    │       ⬇️ 计算文件特征指纹 (Regex Signature)
    │       ⬇️ 查 L2 LocalCache (智能指纹库)
    │       ✅ 命中! (Log: "[智能记忆] ⚡ 命中加速: 间谍过家家 (ID: 120089)")
    │       ⚠️ 标记 Context: has_fingerprint = True, 锁定 TMDB ID
    │
    ├── 2. [ParserStage] 文件名解析阶段
    │       │
    │       ⬇️ [Step 1: 预处理与自定义规则]
    │    [L1 TitleCleaner] -> 剔除干扰词、应用自定义规则
    │       (Log: "清洗后结果: ...")
    │       │
    │       ⬇️ [Step 1.5: 特权提取 (标题 + 集数)] ⭐ NEW
    │    [L1 SpecialEpisodeHandler] -> 匹配外部特权规则
    │       ✅ 命中规则 -> 锁定集数、提取标题作为优先搜索词
    │       (Log: "[规则][特权] LoliHouse 定向命中")
    │       (Log: "┣ 标题: Spy x Family")
    │       (Log: "┣ 集数: 13")
    │       │
    │       ⬇️ [Step 2: 元数据独立探测]
    │    [L1 TagExtractor] -> 提取年份、季号、发布平台
    │       (Log: "[规则][内置] 上映年份: 2025")
    │       │
    │       ⬇️ [Step 2.5: 规格预处理与噪声屏蔽]
    │    [L1 Shield Engine] -> 提取并屏蔽技术规格
    │       提取: 分辨率、视频编码、音频编码、制作组
    │       (Log: "[规则][内置] 分辨率标准化: 1080p -> 1080P")
    │       │
    │       ⬇️ [Step 3: Anitopy 语义内核]
    │    [L1 AnitopyWrapper] -> 解析标题、集数、季号
    │       📝 即使命中特权规则，仍需运行此步以补全其他信息
    │       (Log: "[RAW] anime_title: Spy x Family")
    │       │
    │       ⬇️ [Step 4-7: 后处理与精炼]
    │    [L1 PostProcessor] -> 属性对撞、合集处理、标题修正
    │       合并特权提取结果与 Anitopy 结果
    │
    ├── 3. [MatcherStage] 数据对撞匹配阶段 (智能跳过!)
    │       ❓ 检查 Context: 是否已有锁定 ID?
    │       ✅ 是 (来自智能记忆) -> ⏩ 跳过耗时的数据库/API 搜索
    │       ❌ 否 -> 进入常规匹配流程
    │           ⬇️ 优先使用特权标题搜索 (如有)
    │           ⬇️ 本地 DB -> 在线 API -> L1 对撞
    │
    ├── 4. [EnrichmentStage] 元数据补全阶段
    │       ⬇️ 已知 ID, 请求详细信息
    │    [L2 TMDBProvider] -> get_details(id)
    │       ⬇️ 获取: 官方标题, 简介, 海报, 演职员
    │       🛡️ [用户修正检查] -> 检查是否有 "User Fix" 记录并覆盖
    │
    └── 5. [Finalize] 渲染与输出
            ⬇️ 应用用户自定义渲染规则 (RenderEngine)
            ⬇️ 二级分类计算 (Classifier)
            ⬇️ 写入/刷新智能记忆 (Maintenance)
            ⬇️ 生成最终 JSON 响应
```

---

## 📋 内核处理步骤详解 (Kernel Steps)

### STEP 1: 预处理与自定义规则

**执行组件**: `title_cleaner.py`

| 操作 | 说明 |
|------|------|
| 路径分隔符脱敏 | 强制单文件模式下，将 `/` 替换为特殊标记，防止路径被误解析 |
| 自定义规则应用 | 应用用户的 `替换词 => 目标词` 规则，支持正则表达式 |
| 干扰词清洗 | 剔除 `1080p`、`HEVC`、`AAC` 等规格词，为后续处理提供纯净输入 |
| 强制元数据注入 | 支持 `关键词 => {[tmdbid=12345]}` 格式直接锁定 TMDB ID |

**示例日志：**
```
┣ 原始文件名: [LoliHouse] Spy x Family - 13 [1080p].mkv
┣ 清洗后结果: [LoliHouse] Spy x Family - 13
```

### STEP 1.5: 特权提取 (标题 + 集数) ⭐

**执行组件**: `special_episode_handler.py`

**这是优先级最高的提取步骤！**

| 特性 | 说明 |
|------|------|
| 执行时机 | 在预处理之后、元数据探测之前 |
| 规则来源 | 外部配置文件 / 远程 URL / 数据库缓存 |
| 提取内容 | 字幕组、标题、集数（集数可选） |
| 集数锁定 | 命中后集数**不可被覆盖**，后续流程无法修改 |
| 标题优先 | 提取的标题作为**优先搜索词**，提高匹配准确率 |
| 支持电影 | 集数索引填 `无` 可只提取标题，适用于电影/剧场版 |

**规则格式：**
```
正则表达式|||字幕组索引|||标题索引|||集数索引|||描述
```

**示例规则：**
```
^\[(LoliHouse)\]\s+(.+?)\s+-\s+(\d{1,4})|||1|||2|||3|||LoliHouse 定向
^\[(MyGroup)\]\s+(.+?)\s+\[BD\]|||1|||2|||无|||电影标题提取
```

**示例日志：**
```
┃ [DEBUG][STEP 1.5: 特权提取 (标题 + 集数)]: 启动子流程审计
┣ [规则][特权] LoliHouse 定向命中
┣ ┣ 字幕组: LoliHouse
┣ ┣ 标题: Spy x Family
┣ ┣ 集数: 13
┣ ┣ [Shield] 特权集数已从标题中剥离: 13
┣ 清洗后结果: [LoliHouse] Spy x Family [1080p].mkv
┗ ✅ 流程结束
```

### STEP 2: 元数据独立探测

**执行组件**: `tag_extractor.py`

在进入 Anitopy 之前，**提前提取**关键元数据，避免被后续清洗流程误删：

| 提取项 | 正则模式 | 说明 |
|--------|----------|------|
| 年份 | `\b((19\|20)\d{2})\b` | 4位数字年份，如 `2024` |
| 季号 | `S\d+`、`第X季`、罗马数字 | 支持中英文和罗马数字，如 `S02`、`第二季`、`III` |
| 发布平台 | CR、NF、AMZN、ATVP 等 | 流媒体平台标识，自动映射为全称 |

**平台映射表：**
| 缩写 | 全称 |
|------|------|
| CR | Crunchyroll |
| NF | Netflix |
| AMZN | Amazon |
| ATVP | AppleTV+ |
| DSNP | Disney+ |

**示例日志：**
```
┃ [DEBUG][STEP 2: 元数据独立探测]: 启动子流程审计
┣ [规则][内置] 上映年份: 2024
┣ [规则][内置] 季号: S2
┗ ✅ 流程结束
```

### STEP 2.5: 规格预处理与噪声屏蔽

**执行组件**: `kernel.py` (Shield Engine)

这是内核中最复杂的步骤之一，负责提取并屏蔽所有技术规格：

#### 制作组提取

| 策略 | 说明 |
|------|------|
| 全局扫描 | 扫描整个文件名，匹配自定义制作组列表 |
| 智能扩张 | 发现锚点后向左右扩张，捕获联合发布块 (GroupA & GroupB) |
| 首部检测 | 检测文件名开头的 `[字幕组]` 格式 |
| 特征词校验 | 包含中文/日文时，必须包含制作组特征词（字幕组、制作、社等） |

#### 技术规格提取

| 提取项 | 正则模式 | 标准化输出 |
|--------|----------|------------|
| 分辨率 | `1080p`、`2160p`、`4K` | 1080P、4K |
| 视频编码 | `x265`、`HEVC`、`H.264` | H.265、H.264 |
| 音频编码 | `Atmos5.1`、`DTS-HD`、`AAC` | Dolby Atmos 5.1、DTS-HD MA、AAC |
| 来源 | `WEB-DL`、`Blu-ray`、`WebRip` | WEB-DL、Blu-ray、WebRip |
| 视频特效 | `HDR`、`HDR10+`、`Dolby Vision` | HDR、HDR10+、Dolby Vision |
| 字幕语言 | `简繁内封`、`双语`、`CHS&CHT` | 简繁内封、简日双语 |

#### 噪声屏蔽

| 类型 | 示例 |
|------|------|
| 文件容器 | MKV、MP4、AVI、TS |
| 完结标志 | Fin、END、Complete、完结 |
| 修正标签 | 精校、修正、修复、重制 |
| 残余碎片 | 字幕、样式、特效、版本 |

**示例日志：**
```
┃ [DEBUG][STEP 2.5: 规格预处理与噪声屏蔽]: 启动子流程审计
┣ ┣ [Shield] 全局匹配命中制作组(含联合扩张): MILKs&LoliHouse
┣ [规则][内置] 分辨率标准化: 1080p -> 1080P
┣ [规则][内置] 视频规格: HEVC -> H.265
┣ [规则][内置] 音频规格: AAC -> AAC
┣ [规则][内置] 介质来源: WebRip -> WebRip
┣ ┣ [Shield] 清除文件容器: mkv
┣ [规则][规范化] 字幕语言: 简繁内封
┣ 清洗后结果: Spy x Family 13
┗ ✅ 流程结束
```

### STEP 3: Anitopy 语义内核

**执行组件**: `anitopy_wrapper.py`

调用 Anitopy 库进行语义解析，这是传统的动漫文件名解析器：

| 输出字段 | 说明 |
|----------|------|
| `anime_title` | 动画标题 |
| `episode_number` | 集数 |
| `episode_title` | 集标题 |
| `anime_season` | 季号 |
| `release_group` | 发布组 |
| `video_resolution` | 分辨率 |
| `video_term` | 视频编码 |
| `audio_term` | 音频编码 |

**重要说明：**
- 即使命中特权规则，此步骤仍会执行
- 用于补全特权规则未提取的信息
- 特权提取的集数优先级高于 Anitopy

**示例日志：**
```
┃ [DEBUG][STEP 3]: 调用 Anitopy 语义内核
┣ [RAW] episode_number: 13
┣ [RAW] anime_title: Spy x Family
┗ ✅ 内核解析完成
```

### STEP 4-7: 后处理与精炼

**执行组件**: `post_processor.py`

| 步骤 | 操作 | 说明 |
|------|------|------|
| STEP 4 | 属性对撞与同步 | 合并各步骤提取的结果，优先级：特权 > Anitopy > 独立探测 |
| STEP 5 | 标题标准化 | 清理标题中的特殊字符，处理多语言标题拆分 |
| STEP 6 | 合集处理 | 处理 `[01-12]` 格式的合集范围，生成 episode_range |
| STEP 7 | 智能记忆应用 | 应用历史匹配记录中的标题映射 |

**属性优先级规则：**
```
集数: 特权提取 > Anitopy > 独立探测
标题: 特权提取 (优先搜索) + Anitopy (备选)
季号: 强制规则 > Anitopy > 独立探测
```

**示例日志：**
```
┃ [DEBUG][STEP 4: 属性对撞与同步]: 启动子流程审计
┣ [规则][内置] 集数校验通过: E13
┗ ✅ 流程结束
```

---

## 🔬 真实日志对照解析

以下是对真实运行日志的逐行技术解读：

| 日志片段 | 对应层级/组件 | 技术含义 |
| :--- | :--- | :--- |
| `🚀 --- [ANIME 深度审计流水线启动] ---` | **L3 Orchestrator** | 工作流 Context 初始化，加载全局配置快照。 |
| `┃ [待处理条目]: [LoliHouse] Spy x Family - 13.mkv` | **L3 Orchestrator** | 记录原始输入，便于调试追踪。 |
| `┃ [配置] 策略状态: 动漫优化[ON] \| 合集增强[ON]...` | **L3 Orchestrator** | 显示当前启用的识别策略。 |
| `[智能记忆] ⚡ 命中加速: ... (ID: 120089)` | **L2 LocalCache** | **关键路径分支**：计算文件名特征后，在本地 KV 库中找到了历史匹配记录。直接锁定了 TMDB ID，后续的 Matcher 阶段将被旁路。 |
| `[DEBUG][STEP 1: 预处理...]` | **L1 TitleCleaner** | 正则清洗。去除了干扰词，为后续处理提供更纯净的输入。 |
| `[DEBUG][STEP 1.5: 特权提取...]` | **L1 SpecialEpisodeHandler** | **优先级最高**。匹配外部特权规则，命中后锁定集数并提取标题。 |
| `[规则][特权] LoliHouse 定向命中` | **L1 SpecialEpisodeHandler** | 特权规则命中，集数已锁定，标题作为优先搜索词。 |
| `[DEBUG][STEP 3]: 调用 Anitopy ...` | **L1 Kernel** | **必须执行**。即使 ID 已知，仍需知道当前文件是"第几集"。 |
| `[匹配] 🎯 使用特权标题优先搜索: ...` | **L3 Matcher** | 特权提取的标题被用于优先搜索，提高匹配准确率。 |
| `[数据中心] 🔍 正在调取深度档案...` | **L3 Enricher** | 拿着 ID 去 L2 数据层（本地数据库或 TMDB）换取完整的元数据（海报、简介等）。 |
| `🛡️ [数据中心] 命中用户修正记录` | **L2 OfflineDAO** | **数据覆盖**。系统发现用户曾在"智能修正"中手动指定过此 ID 的映射关系，优先级最高，确保 100% 准确。 |
| `✅ [二级分类] 档案同步完成` | **L1 Classifier** | 根据元数据（如流派、国家）和用户配置的规则，计算文件应归档到的二级目录。 |
| `⏱️ [性能审计]: 全链路耗时 86ms` | **L3 Audit** | **性能体现**。得益于智能记忆命中，整个识别过程仅耗时 86ms。 |

---

## 🧩 各层级深度解析 (Detailed Component Breakdown)

### 1. Level 1: 识别内核 (Kernel)

> **设计目标**：可移植、可独立打包 (.so/.pyz)、极速、无副作用。

**物理位置**: `backend/recognition_engine/`

#### 关键组件详解

##### `kernel.py` - 内核入口
- **职责**: 编排 STEP 1-7 的执行顺序，管理数据流转
- **输入**: 原始文件名、自定义规则、配置选项
- **输出**: `MetaBase` 对象（包含所有提取的元数据）
- **特点**: 无 I/O 操作，纯函数式设计

##### `special_episode_handler.py` - 特权提取器
- **职责**: 在 STEP 1.5 执行，匹配外部规则提取标题和集数
- **规则来源**: 外部配置文件 / 远程 URL / 数据库缓存
- **优先级**: 最高，命中后集数直接锁定
- **支持格式**: 字幕组 + 标题 + 集数，或仅标题（电影模式）

##### `anitopy_wrapper.py` - Anitopy 封装
- **职责**: 封装底层 Anitopy 库，将文件名拆解为字典
- **输出字段**: anime_title, episode_number, anime_season, release_group 等
- **特点**: 语义级解析，能理解动漫文件名的常见格式

##### `title_cleaner.py` - 预处理清洗
- **职责**: 剔除干扰词、处理路径、应用自定义规则
- **清洗内容**: 分辨率、编码、介质、平台等规格词
- **特点**: 支持正则替换，支持强制元数据注入

##### `tag_extractor.py` - 独立探测
- **职责**: 使用正则提取分辨率、音频、视频、制作组等
- **特点**: 不依赖 Anitopy，独立运行
- **提取项**: 年份、季号、平台、分辨率、编码、字幕语言

##### `post_processor.py` - 后处理
- **职责**: 合并各步骤结果，处理合集，应用智能记忆
- **优先级规则**: 特权 > Anitopy > 独立探测
- **特殊处理**: 多语言标题拆分、合集范围计算

##### `batch_helper.py` - 合集引擎
- **职责**: 处理 `[01-12]` 格式的合集范围
- **输出**: episode_min, episode_max, episode_range
- **支持格式**: `[01-12]`、`[01~12]`、`E01-E12`

##### `data_models.py` - 数据模型
- **职责**: 定义 `MetaBase` 类，存储所有提取的元数据
- **字段**: type, title, year, season, episode, resolution, codec 等
- **特点**: 支持序列化为 JSON

##### `constants.py` - 常量定义
- **内容**: 所有正则模式、映射表、关键词列表
- **包括**: SEASON_PATTERNS, EPISODE_PATTERNS, NOISE_WORDS, GROUP_KEYWORDS 等

---

### 2. Level 2: 数据供应 (Data Provider)

> **设计目标**：统一接口，屏蔽上游 API 的差异与网络波动。

**物理位置**: `backend/recognition/data_provider/`

#### 关键组件详解

##### `offline.py` (OfflineDAO) - 本地极速拦截
- **职责**: 直接查询本地 PostgreSQL 数据库
- **索引**: 基于 `pg_trgm` 三元组索引，支持模糊匹配
- **性能**: 5ms 内完成匹配，无需联网
- **覆盖率**: 95% 的识别请求可在此完成

##### `tmdb/client.py` - TMDB API 封装
- **职责**: 封装 TMDB API，处理搜索和详情获取
- **特性**:
  - 自动重试机制
  - 语言回退 (zh-CN → ja-JP → en-US)
  - API Key 轮换
  - 请求限流

##### `bangumi/client.py` - Bangumi API 封装
- **职责**: 封装 Bangumi API，用于动漫类资源的辅助匹配
- **适用场景**: 新番、冷门番、TMDB 缺失条目
- **特点**: 专注于 ACG 内容，元数据更丰富

##### `local_cache.py` - 智能指纹缓存
- **职责**: 处理文件系统的指纹缓存 (Series Fingerprint)
- **存储**: SQLite / PostgreSQL
- **生命周期**: 永久，直到用户手动清除
- **性能**: 实现毫秒级二次识别

---

### 3. Level 3: 流程编排 (Pipeline)

> **设计目标**：业务逻辑的组装者，灵活调整识别策略。

**物理位置**: `backend/recognition/pipeline/`

#### 关键组件详解

##### `parser.py` (ParserStage) - 解析阶段
- **职责**: 驱动 L1 内核进行文件名解析
- **调用顺序**: TitleCleaner → SpecialEpisodeHandler → TagExtractor → Anitopy → PostProcessor
- **输出**: 填充完整的 `MetaBase` 对象

##### `matcher.py` (MatcherStage) - 匹配阶段
- **职责**: 核心调度器，实现数据对撞匹配
- **决策树**:
  1. 检查智能记忆是否命中 → 命中则跳过
  2. 查本地数据库 (L2 Offline)
  3. 若未命中，查智能指纹 (L2 Cache)
  4. 若未命中，决定是查 Bangumi 还是 TMDB (根据配置策略)
  5. 拿到数据后，扔给 L1 对撞机计算得分
- **特权标题**: 优先使用特权提取的标题进行搜索

##### `enricher.py` (EnrichmentStage) - 补全阶段
- **职责**: 获取详细元数据，加载用户修正
- **操作**:
  - 调用 TMDB/Bangumi 获取详情
  - 加载海报、简介、演职员
  - 检查并应用用户修正记录
  - 计算二级分类

##### `maintenance.py` - 维护阶段
- **职责**: 识别成功后的数据维护
- **操作**:
  - 写入智能记忆
  - 更新本地缓存
  - 同步数据中心

---

### 4. API 接口层 (Interface)

**物理位置**: `backend/routers/recognition.py`

#### 职责

- 接收 POST 请求 `{ "filename": "..." }`
- 参数校验与预处理
- 初始化 `Context` 状态容器
- 启动 `Pipeline` 工作流
- 序列化结果为 JSON 返回

#### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/recognize` | POST | 单文件识别 |
| `/api/recognize/batch` | POST | 批量识别 |
| `/api/recognize/preview` | POST | 预览识别结果 |

---

## ⚙️ 特性亮点

### 特权提取 (Privileged Extraction)
支持外部配置的正则规则，在流程最早期锁定集数和标题。
- **规则优先级最高**：确保特定字幕组的命名格式 100% 准确识别
- **支持远程规则**：可通过 URL 同步最新规则
- **支持电影模式**：集数可选，适用于电影/剧场版

### 离线优先 (Offline-First)
系统内置 PostgreSQL 镜像库（满血版数据）。
- **95% 识别请求无需联网**
- **毫秒级响应速度**
- **规避 API 限制**

### 智能记忆 (Fingerprint)
一旦某个生僻命名被成功识别，系统会记录该特征。
- **二次识别秒级完成**
- **支持手动修正记忆**
- **自动学习新格式**

### 逻辑与数据隔离
L1 内核不含任何数据库或网络代码。
- **可独立打包部署**
- **支持边缘计算**
- **易于测试和维护**

---

## 📊 性能指标

| 场景 | 耗时 | 说明 |
|------|------|------|
| 智能记忆命中 | ~50ms | 跳过搜索，直接返回 |
| 本地数据库命中 | ~100ms | pg_trgm 模糊匹配 |
| 在线 API 搜索 | ~500ms | TMDB/Bangumi API 调用 |
| 特权规则命中 | +0ms | 无额外开销，提前锁定 |

---

## 🔧 配置选项

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `animePriority` | 动漫识别优化 | ON |
| `batchEnhancement` | 合集增强 | ON |
| `offlinePriority` | 本地数据中心优先 | OFF |
| `bangumiPriority` | Bangumi 数据源优先 | OFF |
| `bangumiFailover` | Bangumi 故障转移 | OFF |
| `forceFilename` | 强制单文件模式 | OFF |
| `seriesFingerprint` | 智能记忆 | OFF |
