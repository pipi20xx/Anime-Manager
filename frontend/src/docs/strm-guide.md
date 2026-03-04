### 虚拟库构建器 (STRM) 指引

原理：生成包含 URL 的 `.strm` 文件

#### 1. 链接构造器 (Link Builder)

系统根据 **URL 前缀** 拼接文件的 **相对路径**。

*   **默认模式:** 默认为空，不填写前缀。STRM 将使用相对路径。
*   **本地路径映射:**
    *   假设源路径: `/NVME/docker2/clouddrive2-19798/medata/CloudDrive/123云盘/新番连载/BT`
    *   链接前缀: `/CloudDrive/123云盘/新番连载/BT/`
    *   生成结果: `/CloudDrive/123云盘/新番连载/BT/Movie.mkv`
    *   > **说明**：目标目录看您自己映射到哪里，关键是链接前缀结尾必须带 `/`
*   **网盘直链 (CD2):**
    *   假设源路径: `/NVME/docker2/clouddrive2-19798/medata/CloudDrive/123云盘/新番连载/BT`
    *   链接前缀: `http://192.168.50.12:19798/static/http/192.168.50.12:19798/False//123云盘/新番连载/BT/`
    *   生成结果: `http://192.168.50.12:19798/static/http/192.168.50.12:19798/False//123云盘/新番连载/BT/Movie.mkv` (URL编码后的完整链接)
    *   > **说明**：如果是 HTTP 直链，必须完整填写 CD2 的静态代理地址（包含 `/False//...`），且结尾必须带 `/`

#### 2. CloudDrive2 Webhook 集成

支持秒级响应的文件变动通知。当 CD2 中有新资源创建时，番剧管家会自动根据任务配置生成 STRM 和同步元数据。

**Webhook 地址：** `http://{你的IP}:8000/api/webhook/cd2/file_notify/` (配置于 CD2 容器的 `/Config/webhook.toml` 中)

> **⚠️ 自动化执行的关键配置**
>
> 1. **CD2 挂载点设置：** 必须在 **[下载器设置]** -> **[CloudDrive2 客户端]** 中正确填写 **“CD2 本地挂载点”**。
>    *   例如：如果您的网盘挂载在本地的 `/medata/CloudDrive`，则此处必须填 `/medata/CloudDrive`。
>    *   **原理：** Webhook 发送的是网盘内部路径（如 `/网盘A/movie.mkv`），系统通过该挂载点将其转换为本地路径（`/medata/CloudDrive/网盘A/movie.mkv`）后再与 STRM 任务进行匹配。
> 2. **URL 结尾：** CD2 的 Webhook URL 结尾必须包含 `/`，否则路径拼接会导致 404 错误。
> 3. **任务开关：** 确保 STRM 任务配置中的 **"响应 CD2 Webhook 推送"** 开关已开启（默认开启）。

#### 3. Emby/Jellyfin Webhook 集成

支持接收 Emby/Jellyfin 的媒体库事件通知，并自动转发到 Telegram。

**Webhook 地址：** `http://{你的IP}:8000/api/webhook/emby`

> **⚠️ Emby 配置指南**
>
> 在 Emby 设置的 **控制面板 -> Webhook** 中添加该地址，并确保以下设置：
> *   **发送格式：** JSON
> *   **勾选事件：**
>     *   媒体库 - 已添加新媒体
>     *   神医助手 - 媒体深度删除
> *   **勾选行为：** 按剧集和专辑对通知进行分组
>
> **功能说明：**
> *   **已添加新媒体：** 当有新的媒体入库时，会发送包含标题、评分、类型、剧情简介等详细信息的 Telegram 通知
> *   **媒体深度删除：** 当在 Emby 中删除媒体时，会发送包含被删除文件列表的 Telegram 通知
>
> **示例通知格式：**
>
> 新入库通知：
> ```
> 📺 新入库 剧集 天穗之咲稻姬 S01E02
> ⭐️ 评分：7.9/10
> 📚 类型：剧集
> 🕒 时间：2026-03-02 17:07:34
>
> 📝 剧情：遥远的最东方，雅那特国。自古以来，人们就相信这片土地上有两个世界...
> ─── 来自 Emby Webhook ───
> ```
>
> 深度删除通知：
> ```
> Emby深度删除
>
> S01E02 - Kamen.Rider.ZEZTZ.S01E02.2025.1080p.Baha.WEB-DL.H.264.AAC-FROGWeb.mkv
> S01E03 - Kamen.Rider.ZEZTZ.S01E03.2025.1080p.Baha.WEB-DL.H.264.AAC-FROGWeb.mkv
> ...
>
> ─── 来自 Emby Webhook ───
> ```
