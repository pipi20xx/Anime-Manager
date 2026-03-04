# 🌸 番剧管家 (Anime Manager)

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Vue3](https://img.shields.io/badge/Frontend-Vue%203-4FC08D?style=flat-square&logo=vue.js)](https://vuejs.org/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Deployment-Docker-2496ED?style=flat-square&logo=docker)](https://www.docker.com/)

**番剧管家** 是一款专为二次元资源管理设计的自动化工具。集成了 AI 增强识别、RSS 订阅下载、自动化文件整理、STRM 生成、Webhook 回调等全链路功能。

---

## 🚀 核心特性

### 🔍 智能识别引擎
- **多层识别架构**: 支持纯净识别内核、数据适配层、业务编排层的解耦设计
- **多数据源集成**: 深度集成 TMDB、Bangumi 及 PostgreSQL 离线元数据中心
- **AI 辅助纠错**: 引入 AI 辅助逻辑，提升识别准确率
- **识别日志追踪**: 完整的识别流程记录，支持查看和重试

### 📡 RSS 订阅与自动化下载
- **多源订阅**: 支持多个 RSS 订阅源管理
- **智能规则匹配**: 支持关键词、正则表达式两种模式
- **自动推送**: 匹配成功后自动推送到下载客户端
- **备用链接**: 主链接失败时自动尝试备用链接
- **下载历史**: 完整的下载记录追踪
- **Jackett 集成**: 建议配合 [Jackett](https://github.com/Jackett/Jackett) 使用，统一管理多个索引站资源

### 📂 自动化文件整理
- **多种整理模式**: 移动、复制、软链接、硬链接
- **规范化重命名**: 自动重组为 `Title/Season N/S01E01.mp4` 结构
- **后台任务**: 支持后台异步执行整理任务
- **整理历史**: 完整的整理操作记录

### 🗄️ STRM 生成引擎
- **异步并行扫描**: 生产者-消费者模型，快速扫描大量文件
- **全自动清理**: 智能比对源端与目标端，自动同步增删
- **元数据透传**: 支持 NFO、图片等关联文件自动同步
- **任务管理**: 创建、预览、执行 STRM 同步任务

### 🔗 Webhook 回调
- **Emby/Jellyfin**: 接收媒体库播放和扫描事件
- **CloudDrive2**: 文件变动自动触发整理
- **自动化联动**: 媒体库更新后自动触发识别和整理

### 📊 数据中心
- **离线元数据**: PostgreSQL 存储全量 TMDB 元数据
- **用户映射**: 支持流派、公司、关键词、语言、国家等自定义映射
- **二级分类**: 灵活的元数据分类规则
- **快速搜索**: 基于索引的模糊搜索

### 📅 日历追踪
- **Bangumi 集成**: 支持从 Bangumi 导入番剧
- **播出提醒**: 追追踪番剧的播出日期
- **今日总结**: 每日推送今日更新汇总

### 🔧 系统管理
- **多下载客户端**: 支持 qBittorrent、CD2 等多种下载器
- **日志控制台**: 实时查看系统日志
- **数据库管理**: 支持表结构查看、SQL 查询、数据清理
- **通知推送**: Telegram 通知集成

---

## 🛠️ 技术架构

### 后端 (Backend)
- **Framework**: FastAPI (Asynchronous Python)
- **ORM**: SQLModel / SQLAlchemy 2.0
- **Database**: PostgreSQL 15+
- **Task Queue**: 基于 Asyncio 的内置异步队列
- **Recognition**: 自研识别内核 + AI Integration

### 前端 (Frontend)
- **Framework**: Vue 3 (Composition API) + TypeScript
- **Bundler**: Vite
- **UI/UX**: Naive UI 组件库，响应式布局支持移动端
- **State**: Pinia

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
         - DB_PASS=123456               # 数据库密码
         - DB_NAME=apm                 # 数据库名称
       restart: always
   ```

3. 启动服务：
   ```bash
   docker-compose up -d
   ```

访问 `http://localhost:6868` 即可进入管理界面。

---

### Jackett 配置（推荐）

本项目建议配合 [Jackett](https://github.com/Jackett/Jackett) 使用，统一管理多个索引站资源。

1. 部署 Jackett：
   ```bash
   docker run -d \
     --name jackett \
     -p 9117:9117 \
     -v /your/jackett/config:/config \
     -v /your/jackett/downloads:/downloads \
     ghcr.io/jackett/jackett:latest
   ```

2. 配置 RSS 订阅源：
   在番剧管家的「订阅源」中添加 Jackett 的 RSS 地址：
   ```
   http://your-jackett-ip:9117/torznab/all
   ```

3. 配置索引站：
   在 Jackett Web 界面（`http://localhost:9117`）中添加你常用的动漫索引站（如 Mikan、Nyaa 等）。

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

### 环境变量说明

| 变量名 | 说明 | 默认值 |
|--------|------|---------|
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
/
├── backend/                # FastAPI 后端核心
│   ├── routers/           # API 路由
│   │   ├── rss.py         # RSS 订阅与规则
│   │   ├── organizer.py    # 文件整理
│   │   ├── strm.py        # STRM 生成
│   │   ├── webhook.py     # Webhook 回调
│   │   ├── tmdb_full.py   # 离线元数据
│   │   ├── user_mapping.py # 用户映射
│   │   ├── calendar.py    # 日历追踪
│   │   └── system.py      # 系统管理
│   ├── rss_core/          # RSS 核心逻辑
│   ├── recognition/        # 识别流编排
│   ├── organizer_core/     # 文件整理逻辑
│   ├── strm/               # STRM 生成引擎
│   └── models/            # 数据模型
├── frontend/               # Vue 3 前端工程
│   ├── src/views/          # 视图页面
│   ├── src/components/     # 可复用组件
│   └── src/composables/    # 组合式函数
└── docker-compose.yml      # 一键部署配置
```

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

## 🤝 贡献与声明

本项目仅供学习交流使用，请勿用于非法用途。

---

❤️ 如果这个项目帮到了你，请给一个 Star！
