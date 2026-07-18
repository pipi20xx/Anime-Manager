# 🌸 番剧管家 (Anime Manager)

[![Version](https://img.shields.io/badge/Version-2.3.4-blue?style=flat-square)](./VERSION)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Vue3](https://img.shields.io/badge/Frontend-Vue%203-4FC08D?style=flat-square&logo=vue.js)](https://vuejs.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Deployment-Docker-2496ED?style=flat-square&logo=docker)](https://www.docker.com/)

**番剧管家** 是一款专为二次元资源管理设计的自动化工具。集成了 AI 增强识别、RSS 订阅下载、自动化文件整理、STRM 生成、Emby 联动、Webhook 回调、AI 智能助手等全链路功能。

> ⚠️ **安全提示**: 本项目由 AI 辅助编写，虽然具备用户认证功能，但未经专业安全审计，**不建议直接暴露在公网环境使用**。建议在局域网或通过 VPN 访问。

---

## 🚀 核心特性

### 🔍 智能识别引擎
- **多层识别架构**: 纯净识别内核（`recognition_engine`）、数据适配层（`data_provider`）、业务编排层（`recognition`）三层解耦设计
- **多数据源集成**: 深度集成 TMDB、Bangumi 及 PostgreSQL 离线元数据中心
- **AI 辅助纠错**: 引入 AI 辅助逻辑，提升识别准确率
- **Anitopy 解析**: 内置 Anitopy 动漫文件名解析器，精准提取标题、集数、制作组等信息
- **TMDB 黑名单**: 支持 TMDB 条目黑名单，避免错误匹配
- **识别日志追踪**: 完整的识别流程记录，支持查看和重试
- **批量识别**: 支持批量识别处理，提升效率

### 📡 RSS 订阅与自动化下载
- **多源订阅**: 支持多个 RSS 订阅源管理
- **智能规则匹配**: 支持关键词、正则表达式两种模式
- **聚合订阅**: 支持聚合多源条目与规则历史查看
- **自动推送**: 匹配成功后自动推送到下载客户端
- **备用链接**: 主链接失败时自动尝试备用链接
- **下载历史**: 完整的下载记录追踪
- **Jackett 集成**: 内置 [Jackett](https://github.com/Jackett/Jackett) 客户端，支持索引站资源搜索与统一管理

### 📂 自动化文件整理
- **多种整理模式**: 移动、复制、软链接、硬链接
- **规范化重命名**: 自动重组为 `Title/Season N/S01E01.mp4` 结构
- **后台任务**: 支持后台异步执行整理任务
- **文件浏览器**: 内置文件浏览器，可视化选择源目录与目标目录
- **整理历史**: 完整的整理操作记录，支持失败分析与重试

### 🗄️ STRM 生成引擎
- **异步并行扫描**: 生产者-消费者模型，快速扫描大量文件
- **全自动清理**: 智能比对源端与目标端，自动同步增删
- **CD2 集成**: 支持 CloudDrive2 文件索引与同步
- **树形同步**: 基于目录树的增量同步管理
- **元数据透传**: 支持 NFO、图片等关联文件自动同步
- **任务管理**: 创建、预览、执行 STRM 同步任务

### 🔗 Webhook 回调
- **Emby**: 接收媒体库播放和扫描事件，支持 Emby 媒体库索引同步
- **CloudDrive2**: 文件变动自动触发整理，CD2 传输监控
- **自动化联动**: 媒体库更新后自动触发识别和整理

### 📊 数据中心
- **离线元数据**: PostgreSQL 存储全量 TMDB 元数据
- **用户映射**: 支持流派、公司、关键词、语言、国家等自定义映射
- **二级分类**: 灵活的元数据分类规则（Classifier）
- **快速搜索**: 基于索引的模糊搜索
- **数据库管理**: 可视化数据库表结构查看、SQL 查询、数据清理

### 📅 日历追踪
- **Bangumi 集成**: 支持从 Bangumi 导入番剧
- **播出提醒**: 追踪番剧的播出日期
- **今日总结**: 每日推送今日更新汇总

### 🔧 系统管理
- **多下载客户端**: 支持 qBittorrent、CloudDrive2 等多种下载器
- **日志控制台**: WebSocket 实时推送系统日志
- **通知推送**: Telegram 通知集成，支持启动通知、异常告警
- **定时任务**: 基于 APScheduler 的后台定时任务调度
- **文件监控**: 基于 Watchdog 的文件变动监控

### 🤖 AI 智能助手
- **多模型支持**: 支持 OpenAI、Ollama 等 AI 模型接入
- **工具调用**: 内置订阅管理、文件整理、媒体搜索、日历、下载、系统管理等工具
- **技能系统**: 支持自定义技能扩展，内置 5 个技能
- **Telegram Bot**: 通过 Telegram 与 AI 助手交互
- **流式输出**: 支持流式响应，实时显示回复
- **消息摘要**: 智能压缩历史消息，节省 Token 消耗
- **AI 实验室**: 独立的 AI 交互界面，支持多轮对话

### 🔐 认证与安全
- **用户登录**: 支持用户名密码登录
- **双因素认证**: 支持 TOTP 二步验证 (2FA)
- **会话管理**: 多设备登录管理，支持强制下线
- **API Token**: 支持外部 API 访问控制
- **API 审计**: 所有 API 请求自动记录审计日志

### 💓 健康检查
- **文件监控**: 监控本地文件是否存在、可读
- **URL 检测**: 检测远程 URL 可用性
- **定时检查**: 支持自定义检查间隔
- **异常告警**: 检查失败时发送 Telegram 通知

### 📈 任务历史
- **执行记录**: 完整的任务执行历史
- **状态追踪**: 查看任务执行状态和结果
- **重试机制**: 支持失败任务重试

### 🎯 优先级规则
- **质量配置**: 自定义视频质量优先级
- **规则组合**: 支持多规则组合匹配
- **订阅关联**: 与订阅系统深度集成

### 🔍 探索发现
- **TMDB 发现**: 按 genre、年份、语言等维度发现新番
- **Bangumi 推荐**: 基于 Bangumi 标签推荐
- **多源搜索**: 同时搜索 TMDB 和 Bangumi
- **TMDB 详情**: 支持查看 TMDB 条目与人物详情

### 🎨 外观定制
- **主题系统**: 支持自定义主题配色
- **实例定制**: 自定义实例名称、图标等
- **页面定制**: 灵活的页面级外观配置
- **PWA 支持**: 可安装为渐进式 Web 应用

### 🌐 外部控制
- **API 接口**: 完整的 RESTful API
- **Token 认证**: 支持 Bearer Token 认证
- **Webhook**: 支持外部系统回调
- **文件哈希**: 支持文件哈希校验

---

## 🛠️ 技术架构

### 后端 (Backend)
- **Framework**: FastAPI (Asynchronous Python)
- **Server**: Uvicorn + uvloop + httptools（高性能异步）
- **ORM**: SQLModel / SQLAlchemy 2.0 (asyncpg 异步驱动)
- **Database**: PostgreSQL 15+
- **Task Scheduler**: APScheduler + 基于 Asyncio 的内置异步队列
- **File Monitor**: Watchdog
- **Recognition**: 自研识别内核 + Anitopy + AI Integration
- **Auth**: JWT (python-jose) + bcrypt + pyotp (2FA)
- **gRPC**: CloudDrive2 客户端通信

### 前端 (Frontend)
- **Framework**: Vue 3 (Composition API) + TypeScript
- **Bundler**: Vite 6
- **UI/UX**: Naive UI 组件库 + Heroicons 图标，响应式布局支持移动端
- **State**: Pinia
- **PWA**: vite-plugin-pwa 渐进式 Web 应用支持
- **Markdown**: unplugin-vue-markdown 文档渲染支持

---

## 📦 快速部署

### 方式一：使用 Docker 镜像（需要外部 PostgreSQL）

适用于已有 PostgreSQL 数据库的环境。

1. 拉取镜像：
   ```bash
   docker pull pipi20xx/anime-manager:latest
   ```

2. 创建配置文件 `docker-compose.yml`：
   ```yaml
   services:
     apm:
       image: pipi20xx/anime-manager:latest
       container_name: anime-manager
       volumes:
         # 持久化数据（配置、数据库、日志）
         - ./data:/app/data
         # 映射你的媒体目录（可选）
         - /your/media/path:/media
       ports:
         - "6868:8000"
       environment:
         - PYTHONUNBUFFERED=1
         - TZ=Asia/Shanghai
         - DB_HOST=192.168.50.12      # PostgreSQL 服务器地址
         - DB_PORT=5433               # PostgreSQL 端口
         - DB_USER=apm                 # 数据库用户名
         - DB_PASS=123456              # 数据库密码
         - DB_NAME=apm                 # 数据库名称
       restart: always
   ```

3. 启动服务：
   ```bash
   docker-compose up -d
   ```

访问 `http://localhost:6868` 即可进入管理界面。

---

### 方式二：使用 Docker Compose（包含 PostgreSQL）

适用于快速搭建完整环境，一键启动。

1. 创建配置文件 `docker-compose.yml`：
   ```yaml
   services:
     postgres_server:
       image: postgres:16
       container_name: postgres_server
       restart: always
       network_mode: bridge
       environment:
         POSTGRES_USER: root
         POSTGRES_PASSWORD: 123456
         POSTGRES_DB: postgres
       ports:
         - "5433:5432"
       volumes:
         - ./data:/var/lib/postgresql/data

     apm:
       image: pipi20xx/anime-manager:latest
       container_name: apm-matcher
       depends_on:
         - postgres_server
       volumes:
         - ./data:/app/data
         # 映射你的媒体目录
         - /vol1/1000/NVME:/202nvme
       ports:
         - "6868:8000"
       environment:
         - PYTHONUNBUFFERED=1
         - TZ=Asia/Shanghai
         - DB_HOST=postgres_server
         - DB_PORT=5433
         - DB_USER=root
         - DB_PASS=123456
         - DB_NAME=postgres
       restart: always
   ```

2. 启动服务：
   ```bash
   docker-compose up -d
   ```

访问 `http://localhost:6868` 即可进入管理界面。

---

### 方式三：从源码构建（开发调试）

适用于本地开发或自定义修改。

1. 克隆仓库：
   ```bash
   git clone https://github.com/pipi20xx/Anime-Manager.git
   cd Anime-Manager
   ```

2. 使用 Docker Compose 从源码构建：
   ```bash
   docker-compose up -d --build
   ```

   项目根目录已包含 `docker-compose.yml` 和 `Dockerfile`，采用多阶段构建：
   - **Stage 1**: Node 18 构建前端
   - **Stage 2**: Python 3.11 运行后端，挂载前端构建产物

---

### Jackett 部署与配置（推荐）

本项目建议配合 [Jackett](https://github.com/Jackett/Jackett) 使用，统一管理多个索引站资源。可以将 Jackett 直接加入上面的 `docker-compose.yml`，一键部署：

1. 在 `docker-compose.yml` 中添加 Jackett 服务：
   ```yaml
   services:
     # ... 其他服务（postgres_server / apm）...

     jackett:
       image: ghcr.io/jackett/jackett:latest
       container_name: jackett
       restart: always
       ports:
         - "9117:9117"
       volumes:
         - ./jackett/config:/config
         - ./jackett/downloads:/downloads
       environment:
         - TZ=Asia/Shanghai
   ```

2. 启动服务：
   ```bash
   docker-compose up -d
   ```

3. 配置索引站：
   访问 Jackett Web 界面（`http://localhost:9117`），添加你常用的动漫索引站（如 Mikan、Nyaa 等）。

4. 配置 RSS 订阅源：
   在番剧管家的「订阅源」中添加 Jackett 的 RSS 地址：
   ```
   http://your-jackett-ip:9117/torznab/all
   ```

---

### 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DB_HOST` | PostgreSQL 服务器地址 | - |
| `DB_PORT` | PostgreSQL 端口 | 5432 |
| `DB_USER` | 数据库用户名 | - |
| `DB_PASS` | 数据库密码 | - |
| `DB_NAME` | 数据库名称 | - |
| `TZ` | 时区 | Asia/Shanghai |
| `PYTHONUNBUFFERED` | Python 输出缓冲 | 1 |

---

## 📂 项目结构

```text
Anime-Manager/
├── backend/                        # FastAPI 后端核心
│   ├── main.py                     # 应用入口 & 中间件
│   ├── config_manager.py           # 配置管理
│   ├── database.py                 # 数据库连接
│   ├── models.py                   # 数据模型 (SQLModel)
│   ├── auth_utils.py               # 认证工具 (JWT/2FA)
│   ├── notification.py             # Telegram 通知
│   ├── monitor.py                  # 文件监控 & 定时任务
│   ├── logger.py                   # 日志系统 & WebSocket 广播
│   ├── emby_client.py              # Emby 客户端
│   ├── emby_index_service.py       # Emby 媒体库索引服务
│   ├── init_user.py                # 初始化默认用户
│   ├── migrate_subs.py             # 订阅数据迁移
│   ├── entrypoint.sh               # Docker 入口脚本
│   │
│   ├── routers/                    # API 路由
│   │   ├── recognition.py          # 识别接口
│   │   ├── organizer.py            # 文件整理
│   │   ├── strm.py                 # STRM 生成
│   │   ├── rss.py                  # RSS 订阅源与规则
│   │   ├── subscriptions.py        # 订阅管理
│   │   ├── webhook.py              # Webhook 回调
│   │   ├── tmdb.py                 # TMDB 搜索/详情
│   │   ├── tmdb_full.py            # 离线元数据中心
│   │   ├── tmdb_blocklist.py       # TMDB 黑名单
│   │   ├── bangumi.py              # Bangumi 集成
│   │   ├── user_mapping.py         # 用户映射
│   │   ├── calendar.py             # 日历追踪
│   │   ├── assistant.py            # AI 智能助手
│   │   ├── auth.py                 # 认证与安全
│   │   ├── health.py               # 健康检查
│   │   ├── priority.py             # 优先级规则
│   │   ├── explore.py              # 探索发现
│   │   ├── clients.py              # 下载客户端管理
│   │   ├── config.py               # 系统配置
│   │   ├── system.py               # 系统管理
│   │   ├── task_history.py         # 任务历史
│   │   ├── file_hashes.py          # 文件哈希
│   │   ├── appearance.py           # 外观定制
│   │   ├── cache.py                # 缓存管理
│   │   └── sytmdb.py               # 系统 TMDB 配置
│   │
│   ├── recognition/                # 识别流编排层
│   │   ├── recognizer.py           # 识别编排器
│   │   ├── renderer.py             # 渲染器
│   │   ├── ai_helper.py            # AI 辅助
│   │   ├── context.py              # 识别上下文
│   │   ├── data_provider/          # 数据适配层
│   │   │   ├── bangumi/            # Bangumi 数据源
│   │   │   ├── tmdb/               # TMDB 数据源
│   │   │   ├── local_cache.py      # 本地缓存
│   │   │   └── offline.py          # 离线数据
│   │   ├── pipeline/               # 处理管道
│   │   │   ├── parser.py           # 解析器
│   │   │   ├── matcher.py          # 匹配器
│   │   │   ├── enricher.py         # 数据增强
│   │   │   └── maintenance.py      # 维护工具
│   │   └── render/                 # 渲染引擎
│   │       ├── engine.py
│   │       └── reporter.py
│   │
│   ├── recognition_engine/         # 识别引擎内核
│   │   ├── kernel.py               # 识别内核
│   │   ├── anitopy_wrapper.py      # Anitopy 封装
│   │   ├── path_parser.py          # 路径解析
│   │   ├── title_cleaner.py        # 标题清洗
│   │   ├── tag_extractor.py        # 标签提取
│   │   ├── post_processor.py       # 后处理
│   │   ├── special_episode_handler.py  # 特别篇处理
│   │   ├── batch_helper.py         # 批量处理
│   │   ├── builtin_group_loader.py # 内置制作组加载
│   │   ├── bgm_matcher/            # Bangumi 匹配器
│   │   └── tmdb_matcher/           # TMDB 匹配器
│   │
│   ├── rss_core/                   # RSS 核心逻辑
│   │   ├── manager.py              # RSS 管理
│   │   ├── detector.py             # 更新检测
│   │   ├── matcher.py              # 规则匹配
│   │   ├── scheduler.py            # 定时调度
│   │   ├── subscription_manager.py # 订阅管理
│   │   └── subscription_matcher.py # 订阅匹配
│   │
│   ├── organizer_core/             # 文件整理逻辑
│   │   ├── organizer.py            # 整理器
│   │   ├── processor.py            # 处理器
│   │   ├── executor.py             # 执行器
│   │   ├── renamer.py              # 重命名器
│   │   └── file_explorer.py        # 文件浏览器
│   │
│   ├── strm/                       # STRM 生成引擎
│   │   ├── engine.py               # 引擎核心
│   │   ├── strm_generator.py       # STRM 生成器
│   │   ├── processor.py            # 处理器
│   │   ├── scanners.py             # 扫描器
│   │   ├── tree_sync_manager.py    # 树形同步
│   │   ├── cd2_indexer.py          # CD2 索引器
│   │   └── cd2_sync_manager.py     # CD2 同步管理
│   │
│   ├── assistant/                  # AI 助手模块
│   │   ├── agent.py                # Agent 核心（多轮对话/流式输出）
│   │   ├── tools.py                # 工具注册
│   │   ├── skill_engine.py         # 技能引擎
│   │   ├── cache.py                # 对话缓存
│   │   └── builtin_tools/          # 内置工具集
│   │       ├── calendar_tools.py   # 日历工具
│   │       ├── download_tools.py   # 下载工具
│   │       ├── media_tools.py      # 媒体搜索工具
│   │       ├── organize_tools.py   # 整理工具
│   │       ├── subscription_tools.py  # 订阅工具
│   │       └── system_tools.py     # 系统工具
│   │
│   ├── clients/                    # 下载客户端
│   │   ├── base_client.py          # 客户端基类
│   │   ├── manager.py              # 客户端管理器
│   │   ├── qbittorrent.py          # qBittorrent
│   │   ├── cd2.py                  # CloudDrive2
│   │   ├── cd2_helper.py           # CD2 辅助工具
│   │   ├── cd2_monitor.py          # CD2 传输监控
│   │   └── jackett.py              # Jackett
│   │
│   ├── tmdbmatefull/               # TMDB 元数据中心
│   │   ├── database.py             # 数据库操作
│   │   ├── models.py               # 数据模型
│   │   ├── manager.py              # 管理器
│   │   ├── matcher.py              # 匹配器
│   │   ├── classifier.py           # 分类器
│   │   ├── ingestor.py             # 数据导入
│   │   └── browser.py              # 数据浏览
│   │
│   ├── anitopy/                    # Anitopy 文件名解析器
│   ├── metadata/                   # 元数据缓存
│   └── data/logs/                  # 运行日志
│
├── frontend/                       # Vue 3 前端工程
│   ├── src/
│   │   ├── App.vue                 # 根组件
│   │   ├── main.ts                 # 入口
│   │   ├── version.ts              # 版本号
│   │   ├── api/                    # API 请求层
│   │   ├── views/                  # 视图页面
│   │   │   ├── HomeView.vue        # 首页
│   │   │   ├── LoginView.vue       # 登录页
│   │   │   ├── desktop/            # 桌面端视图
│   │   │   │   ├── AiLabViewDesktop.vue        # AI 实验室
│   │   │   │   ├── AppearanceViewDesktop.vue   # 外观定制
│   │   │   │   ├── ExploreViewDesktop.vue      # 探索发现
│   │   │   │   ├── FileBrowserViewDesktop.vue  # 文件浏览器
│   │   │   │   ├── OrganizerViewDesktop.vue    # 文件整理
│   │   │   │   ├── RecognitionLogsDesktop.vue  # 识别日志
│   │   │   │   ├── StrmGeneratorViewDesktop.vue# STRM 生成
│   │   │   │   ├── SubscriptionViewDesktop.vue # 订阅管理
│   │   │   │   ├── SystemLogsViewDesktop.vue   # 系统日志
│   │   │   │   ├── TaskHistoryViewDesktop.vue  # 任务历史
│   │   │   │   ├── JackettSearchViewDesktop.vue# Jackett 搜索
│   │   │   │   ├── ExternalControlDesktop.vue  # 外部控制
│   │   │   │   ├── UsageGuideDesktop.vue       # 使用指南
│   │   │   │   ├── BangumiDetailViewDesktop.vue# Bangumi 详情
│   │   │   │   ├── TmdbDetailViewDesktop.vue   # TMDB 详情
│   │   │   │   ├── TmdbPersonDetailViewDesktop.vue  # TMDB 人物详情
│   │   │   │   └── appearance/     # 外观定制面板
│   │   │   ├── explore/desktop/    # 探索子页面
│   │   │   │   ├── DiscoveryTabDesktop.vue     # 发现
│   │   │   │   ├── RecommendTabDesktop.vue     # 推荐
│   │   │   │   └── SearchTabDesktop.vue        # 搜索
│   │   │   └── settings/           # 设置页
│   │   │       ├── AccountTab.vue              # 账户设置
│   │   │       └── ServiceStatusTab.vue        # 服务状态
│   │   ├── components/             # 可复用组件
│   │   │   ├── desktop/            # 桌面端组件（28+ 模态框/面板）
│   │   │   └── App*.vue            # 通用组件
│   │   ├── composables/            # 组合式函数
│   │   │   ├── components/         # 组件逻辑
│   │   │   ├── explore/            # 探索逻辑
│   │   │   ├── modals/             # 弹窗逻辑
│   │   │   └── views/              # 视图逻辑
│   │   ├── store/                  # Pinia 状态管理
│   │   │   ├── appearanceStore.ts  # 外观状态
│   │   │   ├── navigationStore.ts  # 导航状态
│   │   │   ├── recognitionStore.ts # 识别状态
│   │   │   └── themeStore.ts       # 主题状态
│   │   ├── themes/                 # 主题配置
│   │   ├── styles/                 # 全局样式
│   │   ├── constants/              # 常量定义
│   │   ├── router/                 # 路由配置
│   │   ├── layouts/                # 布局组件
│   │   └── docs/                   # 内置文档
│   ├── public/                     # 静态资源 (PWA)
│   └── scripts/                    # 构建脚本
│
├── skills/                         # AI 技能定义
│   ├── discover-anime/             # 番剧/电影发现
│   ├── subscribe-anime/            # 订阅智能添加
│   ├── subscription-auto-add/      # 本季番剧批量订阅
│   ├── organize-failed-analyze/    # 整理失败分析
│   └── recognize-failed-retry/     # 识别失败重试
│
├── data/                           # 运行数据
│   ├── appearance/                 # 外观配置
│   ├── logs/                       # 日志文件
│   └── tmp/                        # 临时文件（图片缓存等）
│       ├── bgmimg/                 # Bangumi 图片缓存
│       └── tmdbimg/                # TMDB 图片缓存
│
├── Dockerfile                      # 多阶段构建文件
├── docker-compose.yml              # Docker Compose 配置
├── VERSION                         # 版本号
└── README.md                       # 项目文档
```

---

## 🤖 AI 技能系统

番剧管家内置 AI 智能助手，支持通过技能系统扩展能力。以下为内置技能：

| 技能 | 说明 |
|------|------|
| **番剧发现** (`discover-anime`) | 按标签/类型发现番剧或电影，如「我想看科幻番」「推荐一些百合番」 |
| **订阅智能添加** (`subscribe-anime`) | 智能搜索并订阅作品，支持唯一匹配自动订阅、多结果选择 |
| **本季番剧订阅** (`subscription-auto-add`) | 获取当季番剧列表，输入数字快速批量订阅 |
| **整理失败分析** (`organize-failed-analyze`) | 分析整理失败原因并提供重试方案 |
| **识别失败重试** (`recognize-failed-retry`) | 智能分析识别失败原因并提供解决方案 |

技能定义位于 `skills/` 目录，采用 `SKILL.md` 格式，支持自定义扩展。

---

## 📚 自定义规则库

本项目配套的自定义识别词、渲染词、替换词等规则库，托管在 [pipi20xx/555999](https://github.com/pipi20xx/555999) 仓库中。

### 📦 规则文件说明

#### 自定义制作组
- **Group.txt** - 字幕组制作组定义
  - 下载地址: https://raw.githubusercontent.com/pipi20xx/555999/refs/heads/main/anime/Group.txt

#### 自定义替换词
1. **CHSCHTRE.txt** - CHS 替换为简体等
   - 下载地址: https://raw.githubusercontent.com/pipi20xx/555999/refs/heads/main/anime/CHSCHTRE.txt
2. **GroupRE.txt** - 字幕组名字替换
   - 下载地址: https://raw.githubusercontent.com/pipi20xx/555999/refs/heads/main/anime/GroupRE.txt
3. **anime.txt** - 常用替换
   - 下载地址: https://raw.githubusercontent.com/pipi20xx/555999/refs/heads/main/anime/anime.txt
4. **animepisodegroup.txt** - 常用替换（需要搭配剧集组）
   - 下载地址: https://raw.githubusercontent.com/pipi20xx/555999/refs/heads/main/anime/animepisodegroup.txt

#### 自定义渲染词
1. **CHSCHTRE.txt** - CHS 替换为简体等
   - 下载地址: https://raw.githubusercontent.com/pipi20xx/555999/refs/heads/main/anime/CHSCHTRE.txt
2. **GroupRE.txt** - 字幕组名字替换
   - 下载地址: https://raw.githubusercontent.com/pipi20xx/555999/refs/heads/main/anime/GroupRE.txt
3. **animeifre.txt** - 常用替换
   - 下载地址: https://raw.githubusercontent.com/pipi20xx/555999/refs/heads/main/anime/animeifre.txt
4. **episodegroupRE.txt** - 需配合剧集组
   - 下载地址: https://raw.githubusercontent.com/pipi20xx/555999/refs/heads/main/anime/episodegroupRE.txt

#### 自定义特权规则
- **Privileged.txt** - 特权规则（数字表示优先级顺位）
  - 下载地址: https://raw.githubusercontent.com/pipi20xx/555999/refs/heads/main/anime/Privileged.txt

### ⚙️ 特殊规则说明

以下两条规则会自动给 `SXXEXX`、`EPXX` 里面的集号添加中括号：
- **非必要不使用**，不使用源文件名时没有必要使用
- 规则 1: `(S\d+E\d+)(.*)\b(S\d+E\d+)\b => \1\2[\3]`
- 规则 2: `(S\d+E\d+)(.*)\b(E.\d+)\b => \1\2[\3]`

### 📖 使用说明

1. 访问 [pipi20xx/555999](https://github.com/pipi20xx/555999) 仓库查看完整规则
2. 根据需要下载对应的规则文件
3. 将规则文件导入到番剧管家的对应配置中

---

## 🔄 系统启动流程

服务启动时会自动执行以下初始化：

1. **数据库初始化** - 连接 PostgreSQL，创建表结构
2. **元数据缓存** - 初始化本地元数据缓存库
3. **配置加载** - 读取系统配置与规则缓存
4. **内置制作组加载** - 加载内置字幕组制作组定义
5. **默认用户创建** - 确保默认管理员账户存在
6. **CD2 模块预热** - 预热 CloudDrive2 客户端模块
7. **文件监控启动** - 启动 Watchdog 文件监控与定时任务
8. **Emby 索引同步** - 自动同步 Emby 媒体库索引（如已配置）
9. **元数据预热** - 后台预热 Bangumi 日历与 TMDB 热点数据
10. **启动通知** - 发送 Telegram 启动通知（如已配置）

---

## 🤝 贡献与声明

本项目仅供学习交流使用，请勿用于非法用途。

---

❤️ 如果这个项目帮到了你，请给一个 Star！
