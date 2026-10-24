# 全链路识别流水线架构详解 (ANIME Pro Matcher Pipeline)

本文档详细拆解了系统的核心识别引擎架构。该引擎采用高度解耦的分层设计（Layered Architecture），确保了核心算法的纯粹性与数据源的可扩展性。

---

## 🏗️ 核心架构分层概览

系统自上而下分为四层，每一层遵循严格的职责边界：

| 逻辑层级 | 物理路径 (Backend) | 性质 | 核心职能与设计哲学 |
| :--- | :--- | :--- | :--- |
| **API 接口层** | `routers/recognition.py` | **接入** | **(Entry)** 仅负责接收 HTTP 请求与参数校验，不做任何业务处理，直接唤醒 L3 编排器。 |
| **L3 编排层** | `recognition/` | **胶水** | **(Orchestrator)** 业务的大脑。定义识别的"步骤"与"顺序"。它负责指挥 L1 进行解析，指挥 L2 获取数据，并管理全局上下文 (`Context`) 的状态流转。核心入口 `recognizer.py`，状态容器 `context.py`，AI 介入 `ai_helper.py`，结果渲染 `renderer.py` + `render/`。 |
| **L2 数据层** | `recognition/data_provider/` | **I/O** | **(Data Provider)** 系统的手脚。负责一切与"外部"的交互（TMDB API, Bangumi API, 数据库, 文件系统）。**只提供原始数据，不负责判断数据是否匹配。** |
| **L1 内核层** | `recognition_engine/` | **纯逻辑** | **(Kernel)** 系统的核心算法。**纯 CPU 计算，无 I/O，无副作用。** 负责字符串清洗、正则提取、Anitopy 封装、路径解析、制作组加载、以及最关键的"对撞算法"（计算两个标题是否属于同一部番剧）。 |

---

## 🌊 深度全链路数据流转图 (Deep Dive Data Flow)

结合实际运行日志的完整生命周期解析（包含**智能记忆命中**与**特权提取**分支）：

```text
[用户请求] (文件名: "[LoliHouse] Spy x Family - 13 [1080p].mkv")
    ⬇️
[API 层] (routers/recognition.py)
    ⬇️ 1. 启动工作流
[L3 编排层] (recognition/recognizer.py) -> 实例化 Context (recognition/context.py 状态容器)
    │
    ├── 2. [ParserStage] 文件名解析阶段 (recognition/pipeline/parser.py)
    │       │
    │       ⬇️ [锚点溯源与智能懒加载] ⭐
    │    [L3 ParserStage] -> 扫描父级目录（含原始完整路径），嗅探 tmdbid= 锁定 ID，
    │       识别 Season X 季文件夹与 Specials 目录（强制 S0），并判定文件名置信度
    │       (Log: "[路径锁定] 🔐 锁定 ID: 120089")
    │       (Log: "[路径锁定] 📂 识别到季层: S2 (强制类型: TV)")
    │       🛡️ 用户强制 ID (forced_tmdb_id) 优先于路径探测
    │       │
    │       ⬇️ [智能记忆预检] (Fingerprint Check)
    │    [L3 ParserStage] -> 计算文件特征指纹，查 L2 LocalCache (智能指纹库)
    │       ✅ 命中! (Log: "[智能记忆] ⚡ 记忆加速启动，将跳过冗余内核解析步骤")
    │       ⚠️ 锁定 TMDB ID，内核收到 fingerprint_data 后自动简化流程，跳过昂贵的标题拆分
    │       │
    │       ⬇️ [STEP 1: 预处理与自定义规则] (以下进入 L1 内核 core_recognize)
    │    [L1 TitleCleaner] -> 剔除干扰词、应用自定义规则、路径鲁棒性增强
    │       (Log: "清洗后结果: ...")
    │       特性: 支持组合规则(&&)、强制元数据注入、路径分隔符脱敏
    │       │
    │       ⬇️ [STEP 1.5: 特权提取 (标题 + 集数)] ⭐
    │    [L1 SpecialEpisodeHandler] -> 匹配外部特权规则
    │       ✅ 命中规则 -> 锁定集数、提取标题作为优先搜索词、应用额外元数据
    │       (Log: "[规则][特权] LoliHouse 定向命中")
    │       (Log: "┣ 标题: Spy x Family")
    │       (Log: "┣ 集数: 13")
    │       支持字段: group, title, e, s, tmdbid, type(tv/movie/auto), year
    │       │
    │       ⬇️ [STEP 2: 元数据独立探测]
    │    [L1 TagExtractor] -> 提取年份、季号、发布平台
    │       (Log: "[规则][内置] 上映年份: 2025")
    │       新增: 罗马数字季号支持、智能季号探测
    │       │
    │       ⬇️ [STEP 2.5: 规格提取与规范化预处理]
    │    [L1 Shield Engine] -> 提取并屏蔽技术规格
    │       提取: 分辨率、视频编码、音频编码、制作组(含联合扩张)
    │       (Log: "[规则][内置] 分辨率标准化: 1080p -> 1080P")
    │       特性: 制作组智能扩张(支持 & 联合发布)、非括号首部制作组检测
    │       │
    │       ⬇️ [STEP 3: Anitopy 语义内核]
    │    [L1 AnitopyWrapper] -> 解析标题、集数、季号
    │       📝 即使命中特权规则，仍需运行此步以补全其他信息
    │       (Log: "[RAW] anime_title: Spy x Family")
    │       │
    │       ⬇️ [STEP 4-7: 后处理与精炼]
    │    [L1 PostProcessor] -> 属性对撞、集数校验、合集处理、标题修正
    │       新增: 集数智能校验(validate_episode)、尾部集数优先、回捞机制
    │       │
    │       ⬇️ [STEP 2.6: 副标题描述注入] ⭐ (内核返回后执行)
    │    [L1 BatchHelper] -> 从 PT 站副标题/RSS description 提取合集区间/季号特征
    │       (Log: "[STEP 2.6: 副标题描述注入]: 启动检测")
    │       │
    │       ⬇️ [强制参数覆盖] -> 应用 forced_tmdb_id / forced_type / forced_season / forced_episode
    │          (Guard: 智能记忆已命中时，以记忆中的类型为准)
    │
    ├── 3. [MatcherStage] 数据对撞匹配阶段 (recognition/pipeline/matcher.py)
    │       ❓ 检查 Context: 是否已有锁定 ID?
    │       ✅ 是 (来自智能记忆/路径锁定/强制参数) -> ⏩ 跳过耗时的数据库/API 搜索
    │       ❓ 强制 TMDB ID 锁定? -> 优先调取数据中心完整档案 (AUTO 类型按 tv -> movie 双探测)，未命中再联网
    │       ❌ 否 -> 进入常规匹配流程
    │           ⬇️ 特权标题三轮搜索: 原文 -> 清洗后 -> 普通标题 (特权标题含 "/" 时拆分多段，逐段搜索)
    │           ⬇️ 本地 DB (L2 Offline) -> 在线 API (TMDB/Bangumi) -> L1 对撞算法打分
    │           ⬇️ 类型 AUTO? -> 同时搜索 TV + Movie (smart_search_multi)，命中后按结果自动定型
    │           ⬇️ 模糊命中/全 0 分? -> 🛡️ 别名审核 (拉取 TMDB 别名表复核对撞) ⭐
    │       ❓ 常规匹配失败?
    │       ✅ AI 智能介入 (recognition/ai_helper.py) ⭐
    │           ⬇️ 线程池调用 OpenAI 兼容 API 推断真实标题 (guess_title_variants)
    │           ⬇️ 用 AI 返回的标题变体重新搜索云端 -> 本地数据中心
    │           (Log: "[AI 智能体] 🤖 启动 AI 智能介入...")
    │
    ├── 4. [EnrichmentStage] 元数据补全阶段 (recognition/pipeline/enricher.py)
    │       ⬇️ 已知 ID, 请求详细信息
    │    [L2 OfflineDAO] -> get_deep_meta(id) (统一从 MetaCacheManager 获取)
    │       ⬇️ 获取: 官方标题, 简介, 海报, 流派, 国家/语言, 评分 (缺 genre_ids 视为空壳记录)
    │       ⬇️ 空壳记录自动补全 (fetch_and_ingest 抓取 TMDB 全量入库)
    │       🛡️ [用户修正检查] -> is_custom 命中时标题以用户固定名 (custom_title) 覆盖
    │       ⬇️ 计算二级分类 (TmdbFullClassifier, 档案特征: 流派/公司/关键词/国家/语言/年份/标题)
    │       ⬇️ 海报或简介缺失时 -> 联网补全展示资料
    │
    ├── 5. [MaintenanceStage] 维护阶段 (recognition/pipeline/maintenance.py)
    │       ⬇️ 写入/刷新智能记忆 (Fingerprint)
    │       ⬇️ 自动同步元数据到数据中心 (落库存档)
    │       ⬇️ 保护用户修正记录 (is_custom 不被覆盖)
    │
    └── 6. [Finalize] 渲染与输出 (recognition/renderer.py + render/)
            ⬇️ 应用用户自定义渲染规则 (RenderEngine)
            ⬇️ 应用重命名规则 (Renamer)
            ⬇️ 汇报最终结论 (RenderReporter)
            ⬇️ 生成最终 JSON 响应
```

---

## 📋 内核处理步骤详解 (Kernel Steps)

### STEP 1: 预处理与自定义规则

**执行组件**: `title_cleaner.py`

| 操作 | 说明 |
|------|------|
| 路径分隔符脱敏 | 强制单文件模式下，将 `/` 和 `\` 替换为 `_`，防止路径被误解析 |
| 自定义规则应用 | 应用用户的 `替换词 => 目标词` 规则，支持正则表达式、组合规则(`&&`)、强制元数据注入 |
| 干扰词清洗 | 剔除 `1080p`、`HEVC`、`AAC` 等规格词，为后续处理提供纯净输入 |
| 强制元数据注入 | 支持 `关键词 => {[tmdbid=12345;s=1;type=tv]}` 格式锁定多个字段 |
| 装饰符号清除 | 自动清除 `★`, `☆`, `■`, `◆`, `●` 等装饰性符号 |
| 冒号脱敏 | 将 `:` 替换为空格，防止 Anitopy 解析崩溃 |
| 名称叠加防护 | 防止因正则替换产生的名称重复 (如 "字幕组字幕组") |
| 空壳括号清理 | 递归清理被掏空的括号块 (如 `[ ]`, `( )`, `【 】`) |
| 不可见字符清除 | 清除零宽空格等不可见字符 |

**新增特性：**
- **组合规则支持**: 使用 `&&` 连接多条规则，按顺序依次执行
- **集数计算公式**: 使用 `@` 符号表示公式，如 `@+1`, `@*2+1`, `@EP+1`
- **路径鲁棒性增强**: 规则对完整输入未命中时，自动改用文件名部分 (basename) 锚定匹配
- **嵌入式元数据扫描**: 替换生成的 `{[tmdbid=123;s=1]}` 标记会被自动提取为强制元数据并从文件名移除
- **方括号集数归一化**: `[13_OVA]` → `[13]`、`[12end]` → `[12]`
- **连字符集数脱敏**: ` - 01 - ` 结构转为 ` [01] `，防止 Anitopy 递归死锁

**示例日志：**
```
┣ 原始文件名: [LoliHouse] Spy x Family - 13 [1080p].mkv
┣ [规则][私有] 执行正则替换: SumiSora -> UBW
┣ 清洗后结果: [LoliHouse] Spy x Family - 13
```

### STEP 1.5: 特权提取 (标题 + 集数) ⭐

**执行组件**: `special_episode_handler.py`

**这是优先级最高的提取步骤！**

| 特性 | 说明 |
|------|------|
| 执行时机 | 在预处理之后、元数据探测之前 |
| 规则来源 | 用户私有规则 + 社区规则（`[REMOTE]` 前缀标记，同步自远程规则源 RemoteRule 表），由 ParserStage 每次识别前加载 |
| 提取内容 | 字幕组、标题、集数、季数、TMDB ID、媒体类型、年份 |
| 集数锁定 | 命中后集数**不可被覆盖**，后续流程无法修改 |
| 标题优先 | 提取的标题作为**优先搜索词**，提高匹配准确率 |
| 季号剥离 | 特权标题尾部的季号自动剥离（如 `Slime300 S13` → 标题 `Slime300` + 季数 S13），避免搜索词跨季漂移 |
| 多段标题 | 特权标题含 `/` 时拆分为多段，匹配阶段逐段搜索 |
| 制作组剥离 | 命中特权制作组后从标题中剥离（支持 `[组名]` / 尾部 `-组名` / 尾部裸组名三种格式） |
| 支持电影 | 不填 `e` 字段可只提取标题，适用于电影/剧场版 |
| 支持自动类型 | `type=auto` 时同时搜索 TV 和 Movie，自动判断 |

**规则格式：**
```
正则表达式 => {[字段=值;字段=值]} # 规则描述
```

**支持的字段：**
- `group`: 字幕组名称
- `title`: 标题
- `e`: 集数
- `s`: 季数
- `tmdbid`: TMDB ID
- `type`: 媒体类型 (tv/movie/auto)
- `year`: 年份

**type 字段说明：**
- `type=tv` - 强制使用 TV 接口搜索
- `type=movie` - 强制使用 Movie 接口搜索
- `type=auto` - 同时搜索 TV 和 Movie，根据 TMDB 返回结果自动判断类型

**示例规则：**
```
^\[(LoliHouse)\]\s+(.+?)\s+-\s+(\d{1,4}) => {[group=\1;title=\2;e=\3]} # LoliHouse 定向
^\[([^\]]+)\]\s+(.+?)\s+\[BD\] => {[group=\1;title=\2]} # 电影格式
Yami.Shibai.+?(\d+).+?(\d+).+?^[A-Za-z]+$ => {[tmdbid=56559;type=tv;s=\1;e=\2]} # 锁定 TMDB ID
^\[([^\]]+)\]\s+(.+?)\s+-\s+(\d{1,4}) => {[group=\1;title=\2;e=\3;type=auto]} # 自动类型判断
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
| 年份 | `\b((19|20)\d{2})\b` | 4位数字年份，如 `2024` |
| 季号 | `SxxExx`、`S\d+`、`第X季`、罗马数字 | 支持中英文和罗马数字，如 `S02`、`第二季`、`III`、`IV`；已有强制季数时跳过 |
| 发布平台 | CR、NF、AMZN、ATVP 等 | 流媒体平台标识，自动映射为全称；从**原始输入**提取，防止被预处理噪声逻辑误删 |

**新增特性：**
- **罗马数字季号支持**: 支持 `Season III`, `S IV`, `Title III` 等格式
- **罗马数字后缀支持**: 识别标题后的罗马数字 (如 `Title III [01]`，限定 2-10 防误伤)
- **智能季号探测**: 支持中文数字转换 (`第二季` -> `S2`)
- **季号优先级**: 强制季数 > 特权提取 > 独立探测 > Anitopy

**平台映射表（节选）：**
| 缩写 | 全称 |
|------|------|
| CR | Crunchyroll |
| NF | Netflix |
| AMZN | Amazon |
| ATVP | AppleTV+ |
| DSNP | Disney+ |
| LINETV | LINE TV |
| ABEMA | AbemaTV |
| IQ / IQIYI | iQIYI |
| BILI | Bilibili |
| iT | iTunes |
| CRAMZN | Amazon |
| UNEXT | U-NEXT |

**示例日志：**
```
┃ [DEBUG][STEP 2: 元数据独立探测]: 启动子流程审计
┣ [规则][内置] 上映年份: 2024
┣ [规则][内置] 罗马季号: S3
┣ [规则][内置] 发布平台: CR -> Crunchyroll
┗ ✅ 流程结束
```

### STEP 2.5: 规格提取与规范化预处理

**执行组件**: `kernel.py` (Shield Engine)

这是内核中最复杂的步骤之一，负责提取并屏蔽所有技术规格：

#### 制作组提取 (智能扩张机制)

| 策略 | 说明 |
|------|------|
| 联合制作组检测 | 识别 `GroupA & GroupB` 格式，自动扩张为完整制作组名 |
| 全局扫描 | 扫描整个文件名，匹配内置制作组列表 + 自定义制作组列表 |
| 智能扩张 | 发现锚点后向左右扩张，捕获联合发布块 (支持 `&` 和 `@` 连接符) |
| 首部检测 | 检测文件名开头的 `[字幕组]` 格式或非括号首部制作组 |
| 特征词校验 | 包含中文/日文时，必须包含制作组特征词（字幕组、制作、社等） |
| 平台词排除 | 检测并排除平台标识词（CR, NF, AMZN等）被误判为制作组 |

**制作组扩张规则：**
- 向左扩张：遇到 `&` 或空格+`&` 时继续，遇到技术规格词则停止
- 向右扩张：遇到 `&` 或 `@` 时继续，遇到技术规格词则停止
- 边界保护：使用 CJK 边界判定，防止误伤标题的一部分

**示例：**
- 输入: `[MILKs&LoliHouse] Title - 01.mkv`
- 匹配到: `MILKs`
- 智能扩张后: `MILKs&LoliHouse`
- 日志: `[Shield] 全局匹配命中制作组(含联合扩张): MILKs&LoliHouse`

#### 技术规格提取

| 提取项 | 正则模式 | 标准化输出 |
|--------|----------|------------|
| 分辨率 | `1080p`、`2160p`、`4K` | 1080P、4K |
| 视频编码 | `x265`、`HEVC`、`H.264` | H.265、H.264 |
| 音频编码 | `Atmos5.1`、`DTS-HD`、`AAC` | Dolby Atmos 5.1、DTS-HD MA、AAC |
| 音轨标记 | `DUAL`、`MULTI`、`JPN/ENG` | 双音轨、多音轨、日语/英语（并入音频规格） |
| 介质来源 | `WEB-DL`、`Blu-ray`、`WebRip` | WEB-DL、Blu-ray、WebRip |
| 视频特效 | `HDR`、`HDR10+`、`Dolby Vision` | HDR、HDR10+、Dolby Vision |
| 字幕语言 | `简繁内封`、`双语`、`CHS&CHT` | 简繁内封、简日双语 |

#### 噪声屏蔽

| 类型 | 示例 |
|------|------|
| 文件容器 | MKV、MP4、AVI、TS |
| 完结标志 | Fin、END、Complete、Final |
| 合集标志 | 完结、全集、合集 |
| 修正标签 | 精校、修正、修复、重制、无修正 |
| 残余碎片 | 字幕、样式、特效、版本、中字 |
| 多字幕标记 | MSubs、Multi-Subs |
| 别名/检索块 | `[别名:xxx]`、`[检索用:xxx]` 括号块整体屏蔽 (ALIAS_RE) |

**其他预处理：**
- **首部噪声块剔除**: 自动移除开头的 `[搬运]`、`[新番]`、`[连载]`、`[合集]` 等噪声中括号块
- **字幕语言提取优先级**: 先看原始标题，未命中再看预处理后标题（可能命中用户的自定义翻译规则）
- **空壳/孤儿括号清理**: 最多 3 轮递归清理被掏空的括号块与因剥离产生的孤儿括号

**示例日志：**
```
┃ [DEBUG][STEP 2.5: 规格提取与规范化预处理]: 启动子流程审计
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
| STEP 4.5 | 合集增强模式 | 可选（`batchEnhancement`），仅在尚未提取到集数时执行；命中后强制 TV 并补默认季 S1 |
| STEP 5 | 标题残差剥离与拆分 | 清理标题残骸（版本号 V2/V3、站点标签等），处理多语言标题拆分 |
| STEP 6 | 规格属性全量同步 | 同步分辨率、编码、制作组等规格属性（预处理已提取的直接继承） |
| STEP 7 | 最终判定 | 根据元数据确定媒体类型 (TV/Movie)；AUTO 类型延后至匹配阶段由命中结果定型 |

**STEP 4: 集数校验逻辑详解**

`validate_episode` 函数实现了智能集数校验，包含以下机制：

| 机制 | 说明 | 示例 |
|------|------|------|
| 误报拦截 | 检测 `H.264`、`720p` 等技术词被误判为集数 | `H.264` -> 拦截 `4` |
| 尾部集数优先 | 从文件名末尾提取最可靠的集数模式 | `[09]` -> 优先使用 `9` |
| 多集数处理 | Anitopy 返回多个数字时，判断是否为合集范围 | `[1, 2, 3]` -> 合集 `E1-E3` |
| 浮点集数 | 支持 `24.5` 等特别篇集数（整数化的浮点回落为 int） | `24.5` -> E24.5 |

**尾部集数优先级规则：**
```
优先级从高到低:
1. SxxExx 格式 (S01E21) - 最明确，无条件优先
2. 独立集数格式 (E21, EP21, Episode 21)
3. 方括号集数 ([09], [25]) 与混合格式 ([13_OVA], [12end]) - 取最后一个
4. 中文格式 (第21集, 第21话)
5. 连字符格式 (Title - 25) - 需严格校验（后接全大写组名时放弃）
```

**集数范围限制：**
- 合理集数范围：1-500
- 排除分辨率数字：1080, 720, 480, 2160, 360, 576

**STEP 4.5: 合集增强模式 (BatchHelper)**

当启用合集增强模式时，系统会从文件名中深度挖掘合集区间：

**支持的特殊格式：**
- LoliHouse 格式: `[48.5-72(00-24) 合集]`, `[01-08 精校合集]`
- 7³ACG 格式: `\| 01-13(01-25)`
- 标准区间: `[01-12]`, `E01-E12`, `S01E09-E10`
- 中文格式: `第01-13集`, `全12话`

**示例日志：**
```
┃ [DEBUG][STEP 4: 属性对撞与同步]: 启动子流程审计
┣ [规则][内置] 集数校验通过: E13
┣ [BatchHelper] 命中 LoliHouse-General 特色合集规则: 01-12
┗ ✅ 流程结束
```

**属性优先级规则：**
```
集数: 特权提取 > Anitopy > 独立探测 (含尾部优先)
标题: 特权提取 (优先搜索) + Anitopy (备选)
季号: 强制规则 > 特权提取 > Anitopy > 独立探测
制作组: 特权提取 > STEP 2.5 智能扩张 > Anitopy
```

**回捞机制：**
- 从 Anitopy 误判的 `release_group` 中回捞集数（如 `[05_副标题]`）
- 从 SxxExx 格式中回捞季号
- 从标题末尾的技术残骸中回捞制作组
- 从空壳记录中回捞有效标题

**其他保护机制：**
- **指纹直通**: 智能记忆命中时跳过标题残差拆分，媒体类型直接采纳记忆结果
- **电影关键词强制**: 命中剧场版/电影关键词时强制 Movie 并清除集数/季号；集数 > 1900 时判定为年份并修正
- **制作组黑名单核验**: 提取结果经 NOT_GROUPS 黑名单最终核验，防止误判

---

## 🔬 真实日志对照解析

以下是对真实运行日志的逐行技术解读：

| 日志片段 | 对应层级/组件 | 技术含义 |
| :--- | :--- | :--- |
| `🚀 --- [ANIME 深度审计流水线启动] ---` | **L3 Orchestrator** | 工作流 Context 初始化，加载全局配置快照。 |
| `┃ [待处理条目]: [LoliHouse] Spy x Family - 13.mkv` | **L3 Orchestrator** | 记录原始输入，便于调试追踪。 |
| `┃ [配置] 策略状态: 动漫优化[ON] \| 合集增强[ON]...` | **L3 Orchestrator** | 显示当前启用的识别策略。 |
| `[智能记忆] ⚡ 记忆加速启动...` | **L3 ParserStage** | **关键路径分支**：计算文件名特征指纹后，在 L2 LocalCache 智能指纹库中命中历史记录，直接锁定 TMDB ID。内核收到 `fingerprint_data` 后自动简化流程，后续的 Matcher 阶段将被旁路。 |
| `[DEBUG][STEP 1: 预处理...]` | **L1 TitleCleaner** | 正则清洗。去除了干扰词，为后续处理提供更纯净的输入。 |
| `[DEBUG][STEP 1.5: 特权提取...]` | **L1 SpecialEpisodeHandler** | **优先级最高**。匹配外部特权规则，命中后锁定集数并提取标题。 |
| `[规则][特权] LoliHouse 定向命中` | **L1 SpecialEpisodeHandler** | 特权规则命中，集数已锁定，标题作为优先搜索词。 |
| `[DEBUG][STEP 3]: 调用 Anitopy ...` | **L1 Kernel** | **必须执行**。即使 ID 已知，仍需知道当前文件是"第几集"。 |
| `[匹配] 🎯 使用特权标题优先搜索: ...` | **L3 Matcher** | 特权提取的标题被用于优先搜索，提高匹配准确率。 |
| `[数据中心] 🔍 正在调取深度档案...` | **L3 Enricher** | 拿着 ID 去 L2 数据层（本地数据库或 TMDB）换取完整的元数据（海报、简介等）。 |
| `🛡️ [数据中心] 命中用户修正记录` | **L3 Enricher (数据中心档案)** | **数据覆盖**。档案带 `is_custom` 标记（用户设置过 custom_title 固定名），标题以用户修正为准，优先级最高。未命中时日志为 `📖 命中权威索引`。 |
| `✅ [二级分类] 档案同步完成` | **数据中心 TmdbFullClassifier (L3 Enricher 调度)** | 基于作品档案特征（流派/公司/关键词/国家/语言/年份/标题）与用户二级分类规则 (SecondaryRule) 计算归档目录，日志附 `(分类结果: X/未命中)`。 |
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
- **规则来源**: 用户私有规则 + 社区规则缓存（`[REMOTE]` 前缀，RemoteRule 表），由 ParserStage 加载
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
- **字段**: `cn_name` / `en_name`（中英标题）、`year`、`type`（MediaType）、`begin_season`、`begin_episode` / `end_episode`（支持浮点）、`resource_team`（制作组）、`resource_pix`（分辨率）、`resource_type`（介质）、`video_encode`、`video_effect`（动态范围 HDR/DV）、`audio_encode`、`resource_platform`、`subtitle_lang`、`forced_tmdbid`（强制 ID）、`privileged_title`（特权标题，优先搜索词）、`is_batch`（合集）、`tags`、`processed_name`、`original_cn_name` 等
- **特点**: 支持序列化为 JSON

##### `path_parser.py` - 路径解析器
- **职责**: 处理复杂文件路径，嗅探路径中的元数据（如 `tmdbid=12345`）
- **功能**: 智能扁平化目录结构、提取强制 ID、识别季文件夹（Specials → S0）
- **特点**: 支持从父级目录反向溯源元数据
- **现状**: 独立保留组件；路径溯源逻辑已内联进 `pipeline/parser.py`（锚点溯源），主流水线不再直接调用该模块

##### `builtin_group_loader.py` - 内置制作组加载器
- **职责**: 从 `builtin_groups.txt` 加载预置的制作组名单
- **特点**: 单例模式，懒加载，避免重复读取文件

##### `bgm_matcher/` - Bangumi 对撞匹配算法内核
- **职责**: Bangumi → TMDB 的对撞匹配纯算法（无网络请求）
- **功能**: `generate_search_strategies()` 由 Bangumi 条目生成 TMDB 多路搜索词（原名 ja 优先，附截断基名策略）；`score_candidate()` 100 分制打分（文本相似度×60 + 类型一致 +20 / 冲突 -40（TV→Movie 且条目名含总集篇等合集特征时仅 +5）+ 年份精准 +20 / 微差 +10 + 动画 genre +40）
- **调用方**: L2 `data_provider/bangumi/client.py` 的 `map_to_tmdb()`（BGM 数据源优先 / 故障转移策略）；`utils.extract_season_from_name` 另被订阅工具与 Bangumi 路由复用

##### `tmdb_matcher/` - TMDB 对撞匹配算法内核
- **职责**: TMDB 搜索候选的打分与格式归一化纯算法
- **功能**: `calculate_match_score()` 打分体系（精准命中 100 / 包含命中 80 / 模糊=相似度；动画暴击 +40、排名红利 +15/+10/+5、全名搜索 +10、分词惩罚 -15、年份精准 +20 / 微差 +10；过短词防误报），`extra_titles` 参数支持别名表参与对撞，日文候选经 pykakasi 生成罗马音变体参与对撞（`_jp_to_romaji`）；`normalize()` 统一 TMDB 元数据格式（miniseries 等类型修正为 tv）并代理化图片路径；`query_builder.py` 承载多路查询词构建（搜索词受分词开关控制，评分 targets 不受影响）
- **调用方**: L2 `data_provider/tmdb/client.py` 的 `smart_search()`，并复用于 TMDB 详情、探索发现、AI 助手等模块

##### `constants.py` - 常量定义
- **内容**: 所有正则模式、映射表、关键词列表
- **包括**: SEASON_PATTERNS, EPISODE_PATTERNS, NOISE_WORDS, GROUP_KEYWORDS, ALIAS_RE（别名/检索用括号块）等
- **规格值登记区**: SOURCE_TOKENS / VIDEO_ENCODE_RULES / AUDIO_CODEC_RULES / DYNAMIC_RANGE_DEFS 等是识别归一化的唯一事实来源，洗版规则/订阅筛选的下拉选项由此派生 (`rss_core/field_options.py`)

---

### 2. Level 2: 数据供应 (Data Provider)

> **设计目标**：统一接口，屏蔽上游 API 的差异与网络波动。

**物理位置**: `backend/recognition/data_provider/`

#### 关键组件详解

##### `offline.py` (OfflineDAO) - 本地极速拦截
- **职责**: 本地数据中心查询入口，委托 `TmdbMateFullManager.resolve_recognition()` 完成匹配（`pg_trgm` 三元组模糊匹配实现在 `tmdbmatefull/matcher.py`）
- **性能**: 毫秒级完成匹配，无需联网，95% 的识别请求可在此完成
- **深度档案**: 统一通过 `MetaCacheManager.get()` 获取合并后的元数据

##### `tmdb/client.py` - TMDB API 封装
- **职责**: 封装 TMDB API，处理搜索和详情获取
- **特性**:
  - 多路查询分组：原始中文 / 简体中文 (zh-CN) 与英文（同一组英文词在 en-US / zh-CN / zh-TW / ja-JP 四种请求语言下重复查询——TMDB 关键词匹配与罗马音别名依赖请求语言）；分词实现独立于 `recognition_engine/tmdb_matcher/query_builder.py`，受 `enable_title_segmentation` 开关控制（默认关闭，仅用完整标题查询；评分 targets 不受开关影响）
  - 完整标题搜索网络失败自动重试（最多 3 次，仍失败则中止本次识别）；已有候选达 95 分高置信度时剪枝剩余备用查询；全名搜索唯一命中直接采信
  - 搜索无结果时按年份参数自动重试（tv 追加 first_air_date_year / movie 去掉 year）；详情获取失败时用归一化搜索结果兜底
  - 单 API Key、10s 超时、支持代理
  - **别名审核** ⭐: 最佳候选为模糊命中或全 0 分时，拉取 top2 候选的 TMDB alternative_titles 重新对撞打分复核（别名/搜索结果缓存 6 小时）；采信线 80 分，唯一候选 ID 时触发"孤独命中"策略直接放行

##### `bangumi/client.py` - Bangumi API 封装
- **职责**: 封装 Bangumi API，用于动漫类资源的辅助匹配
- **适用场景**: 新番、冷门番、TMDB 缺失条目
- **特点**: 专注于 ACG 内容，元数据更丰富；`search_subject()` 检索 top3 候选并做规格核验（TV 模式排除单集电影/OVA、集数远超条目总量的非首选候选排除）；`map_to_tmdb()` 先查 BangumiData 快速映射表（仅带 tmdb_id 的映射走快速路径），未命中再用 L1 `bgm_matcher` 算法对撞（tv/movie 双阶段、阶段顺序按条目 platform 调整、任一候选达 85 分提前终止、采信阈值 70 分、查询语言 ja-JP / zh-CN）映射为 TMDB 条目
- **长缓存**: 完结超过 30 天的番剧，subject / episodes / characters 原始响应永久缓存在 bangumi_raw_cache，不再请求官方 API

##### `bangumi/service.py` - Bangumi 数据服务
- **职责**: 维护 Bangumi 数据条目表（BangumiDataItem），定期从 bangumi-data 同步
- **用途**: 为 `map_to_tmdb()` 提供快速映射表，加速番剧识别
- **存储**: `bangumi_data_item` 表 + `discover_cache` 同步状态

##### `local_cache.py` (LocalCacheDAO) - 智能指纹缓存
- **职责**: 处理文件系统的指纹缓存 (Series Fingerprint) 和元数据存档
- **存储**: PostgreSQL `series_fingerprint` 表 + `tmdb_deep_meta` 深度档案表
- **生命周期**: 永久，直到用户手动清除
- **性能**: 实现毫秒级二次识别
- **指纹有效性守卫**: 纯季集模式指纹（如 `S#E#.mkv`、`第#话.mkv`）或文件名过短（<10 字符）时跳过记录，防止不同剧集误匹配
- **统一接口**: 指纹与深度档案经 `MetaCacheManager` 直读数据库（深度档案自动合并 full_data 并应用 custom_title 固定名覆盖）；discover 缓存为两级（L1 内存 5 分钟 + DB，过期小时数由调用方指定，默认 12 小时）

---

### 3. Level 3: 流程编排 (Pipeline)

> **设计目标**：业务逻辑的组装者，灵活调整识别策略。

**物理位置**: `backend/recognition/`

#### 关键组件详解

##### `recognizer.py` - 编排主入口
- **职责**: 定义 `RecognitionWorkflow`，串联五个阶段的执行顺序
- **流程**: ParserStage → MatcherStage → EnrichmentStage → MaintenanceStage → ResultRenderer
- **入口**: `MovieRecognizer.recognize_full()` 静态方法

##### `context.py` - 状态容器
- **职责**: 封装单次识别任务的所有配置、日志和中间状态
- **内容**: 配置快照、策略开关、L2 Provider 实例、规则集、性能统计
- **特点**: 每个 API 请求独立一个 Context，互不干扰

##### `ai_helper.py` - AI 智能介入 ⭐
- **职责**: 常规识别失败时，调用 OpenAI 兼容 API 推断真实标题
- **触发条件**: `ai_fallback_enabled` 开启且常规匹配未命中
- **对外入口**: `guess_title_variants()`（单例模式；同步 httpx 调用丢线程池执行，避免阻塞事件循环）
- **输出**: 真实标题、原名、中文名、备选标题、置信度、媒体类型，可附带季号/集数修正
- **特点**: AI 可修正媒体类型/季号并补集数；标题变体先搜云端（AUTO 类型走多类型搜索）再搜本地数据中心

##### `pipeline/parser.py` (ParserStage) - 解析阶段
- **职责**: 驱动 L1 内核进行文件名解析
- **执行顺序**: 锚点溯源（路径锁定）→ 智能记忆预检 → L1 `core_recognize`（STEP 1-7）→ 副标题描述注入 (STEP 2.6) → 强制参数覆盖 (forced_*)
- **智能记忆**: 指纹命中时锁定 TMDB ID 并向内核传递 `fingerprint_data`，内核自动简化流程；强制 ID 优先于路径探测
- **输出**: 填充完整的 `MetaBase` 对象

##### `pipeline/matcher.py` (MatcherStage) - 匹配阶段
- **职责**: 核心调度器，实现数据对撞匹配
- **决策树**:
  1. Context 已有锁定 ID（智能记忆/路径锁定/强制参数）→ 跳过搜索（短路发生在 ParserStage，此处仅判空跳过）
  2. 强制 TMDB ID 锁定模式 → 优先调取数据中心完整档案（以 genre_ids 判定完整性），未命中再联网调取详情；AUTO 类型按 tv → movie 双探测自动定型
  3. 特权标题三轮搜索（原文 → 清洗后 → 普通标题；特权标题含 `/` 时拆分多段逐段尝试），先本地数据库 (L2 Offline) 再云端；本地命中即跳过云端搜索
  4. 云端顺序由 `bangumi_priority` / `bangumi_failover` 策略决定（TMDB/Bangumi），命中判定由 L1 对撞算法内核打分；类型 AUTO 时同时搜索 TV + Movie 并按命中结果自动定型
  5. 常规匹配失败 → AI 智能介入 (ai_helper.py)
- **别名审核**: TMDB 模糊命中或全 0 分时由 L2 tmdb 客户端拉取别名表复核对撞（见 `data_provider/tmdb/client.py`）

##### `pipeline/enricher.py` (EnrichmentStage) - 补全阶段
- **职责**: 获取详细元数据，加载用户修正
- **操作**:
  - 通过 `OfflineDAO.get_deep_meta()` 统一调取深度档案
  - 缺 `genre_ids` 视为空壳记录，自动调 `fetch_and_ingest` 抓取 TMDB 全量入库后重读
  - 检查并应用用户修正记录（`is_custom` / `custom_title` 固定名覆盖标题）
  - 强制映射档案字段（title / original_title / genre_ids / origin_country / release_date / year 等）
  - 计算二级分类（`TmdbMateFullManager.calculate_secondary_categories_with_data` → `TmdbFullClassifier`，特征口径与 TMDB 屏蔽的档案级条件一致）
  - 海报或简介缺失时联网补全展示资料

##### `pipeline/maintenance.py` (MaintenanceStage) - 维护阶段
- **职责**: 识别成功后的数据维护
- **操作**:
  - 写入/刷新智能记忆 (Fingerprint)
  - 自动同步元数据到数据中心 (落库存档)
  - 保护用户修正记录 (`is_custom` 不被覆盖)

##### `renderer.py` + `render/` - 渲染与汇报
- **职责**: 最终结果的渲染、重命名和汇报
- **组件**:
  - `render/engine.py` (RenderEngine): 执行自定义渲染规则
  - `render/reporter.py` (RenderReporter): 汇报最终结论和性能审计
  - `renderer.py` (ResultRenderer): 协调渲染流程，应用重命名规则 (Renamer)

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
| `/api/recognize` | POST | 全链路识别接口（支持单文件、强制参数、临时规则、副标题注入） |
| `/api/tmdb/tv/{tmdb_id}` | GET | 获取剧集季度详情 |
| `/api/ai/test` | POST | AI 实验室：语义解析测试（AI 标题推断，不涉 TMDB 对撞） |
| `/api/ai/fallback-test` | POST | AI 智能介入测试（标题推断 + 调试信息与耗时） |
| `/api/privilege/test` | POST | 特权集数锁定测试（走当前已加载的特权规则，支持自定义正则调试） |

> **💡 相关链路：** TMDB 关键词搜索接口已迁移至 `routers/tmdb.py`；任务/服务状态实时推送走 WebSocket `/ws/events`（EventBroadcaster），无需轮询；识别任务的日志追踪与清理由 `routers/task_history.py` 提供；RSS 识别失败项的重试入口见下节。

---

## 🛡️ RSS 订阅识别链路的外围关卡 (rss_core/subscription_matcher.py)

`/api/recognize` 只覆盖「识别」本身；RSS 抓取条目走 `SubscriptionMatcher.recognize_items()`，在识别引擎外层追加了两道关卡：

```text
[RSS 条目] -> recognize_items()
    ⬇️ MovieRecognizer.recognize_full(force_filename=True, batch_enhancement=True,
    │      description=订阅源开启合集增强时注入条目描述)
    ⬇️ 识别成功 (final_result 带 tmdb_id)
    ├── 1. [TMDB 屏蔽列表检查] (match_tmdb_block) 🛡️ 全局生效，不受订阅源开关控制
    │       ⬇️ 屏蔽列表整轮载入一次: 精确表 ((tmdb_id, media_type) 锚定作品) + 全局条件表 (tmdb_id 留空)
    │       ⬇️ 精确表未命中再过全局条件表 (media_type=all 时对剧集/电影都生效)
    │       ⬇️ 条件分流评估 (_entry_conditions_met):
    │           资源规格键 (team/resolution/video_encode 等) -> field_match.check_conditions
    │           档案级键 (genre_ids/company_ids/keyword_ids/origin_country/
    │                    original_language/year/title) -> TmdbFullClassifier._check_rule_match
    │       ⬇️ 档案级条件按作品 TMDB 档案评估 (resolve_archive_features):
    │           查数据中心 TmdbDeepMeta 构建 build_features 特征（流派/公司/关键词/国家/
    │           语言/年份/标题，与二级分类规则同口径），轮内缓存，档案缺失按"不匹配"处理
    │       ✅ 命中 -> apply_tmdb_block:
    │           写 state=TmdbBlocked 下载历史 (幂等)，使订阅匹配与规则匹配都按"已下载"跳过
    │           整部作品级 (锚定 ID 且无条件) -> 同步标记订阅对应集已下载
    │           资源级 (带条件) -> 只拦本条资源，同作品其他组的资源照常匹配
    │           (Log: "🚫 TMDB屏蔽列表命中（条件: ...），标记已下载")
    ├── 2. [Emby 库存在检查] (受订阅源 check_emby_exists 开关控制)
    │       库内已有 -> 写 state=EmbyExists 历史并标记订阅对应集已下载
    └── 订阅匹配阶段 (match_and_download) 另有屏蔽回溯拦截，
        兜住"识别之后才加入屏蔽"的历史条目
```

**识别失败重试：** 失败条目（recognition_done 且 tmdb_id 为空）可经 `POST /api/feeds/{feed_id}/retry`（单源）或 `POST /api/rss/recognition/retry`（全局）重跑 `recognize_items(retry_failed=True)`。

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
| `batchEnhancement` | 合集增强模式，启用 BatchHelper 深度挖掘合集区间 | OFF |
| `offlinePriority` | 本地数据中心优先 | ON |
| `bangumiPriority` | Bangumi 数据源优先 | OFF |
| `bangumiFailover` | Bangumi 故障转移 | ON |
| `forceFilename` | 强制单文件模式，启用路径分隔符脱敏 | OFF |
| `seriesFingerprint` | 智能记忆 | ON |
| `enableTitleSegmentation` | 标题分词搜索：开启后云端搜索在完整标题外追加分词查询词（评分 targets 始终用完整分词） | OFF |
| `aiFallbackEnabled` | AI 智能介入（需配置 OpenAI 兼容 API） | OFF |

**请求级参数（`/api/recognize` 单次请求可覆盖，优先于全局配置）：**

| 参数 | 说明 |
|------|------|
| `force_filename` | 强制单文件模式（保留完整输入，启用路径分隔符脱敏） |
| `forced_tmdb_id` | 强制锁定 TMDB ID（优先于路径探测） |
| `forced_type` / `forced_season` / `forced_episode` | 强制媒体类型 / 季数 / 集数 |
| `anime_priority` / `offline_priority` / `bangumi_priority` / `bangumi_failover` / `series_fingerprint` / `batch_enhancement` / `enable_title_segmentation` | 单次请求覆盖同名全局策略 |
| `description` | PT 站副标题 / RSS 描述，用于 STEP 2.6 合集特征注入 |
| `temp_noise` / `temp_groups` / `temp_render` / `temp_privilege` | 临时规则沙盒（替换词 / 制作组 / 渲染词 / 特权规则，仅本次请求生效） |


