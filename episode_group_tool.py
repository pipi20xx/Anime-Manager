
"""
TMDB 剧集组生成器 - 独立运行的 PyQt6 桌面工具
根据 TMDB ID 获取剧集信息，并以"季结局(finale)"为界自动划分剧集组。
所有配置（API Key、代理）均在界面内填写，不依赖外部配置文件。
"""

import sys
import json
import asyncio
from typing import Optional, Dict, List

import httpx
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QMessageBox,
    QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings
from PyQt6.QtGui import QFont, QColor

# ─── TMDB API ───────────────────────────────────────────────

TMDB_BASE = "https://api.themoviedb.org/3"


async def _request(url: str, params: dict, proxy: Optional[str] = None, retries: int = 3) -> Optional[Dict]:
    """带重试的 TMDB 请求"""
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=20, proxy=proxy) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    # 速率限制，等待后重试
                    retry_after = int(resp.headers.get("Retry-After", 2))
                    await asyncio.sleep(retry_after)
                    continue
                elif resp.status_code == 401:
                    raise Exception(f"API Key 无效或未授权 (HTTP 401)")
                elif resp.status_code == 404:
                    raise Exception(f"资源不存在 (HTTP 404): {url}")
                else:
                    raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except httpx.TimeoutException:
            if attempt < retries - 1:
                await asyncio.sleep(1)
                continue
            raise Exception(f"请求超时，已重试 {retries} 次")
        except httpx.ConnectError:
            if attempt < retries - 1:
                await asyncio.sleep(1)
                continue
            raise Exception("无法连接到 TMDB 服务器，请检查网络或代理设置")
        except httpx.ProxyError:
            raise Exception("代理连接失败，请检查代理地址是否正确")
    return None


async def fetch_tv_details(tmdb_id: str, api_key: str, proxy: Optional[str] = None) -> Optional[Dict]:
    url = f"{TMDB_BASE}/tv/{tmdb_id}"
    params = {"api_key": api_key, "language": "zh-CN"}
    return await _request(url, params, proxy)


async def fetch_season_episodes(tmdb_id: str, season_number: int, api_key: str, proxy: Optional[str] = None) -> List[Dict]:
    url = f"{TMDB_BASE}/tv/{tmdb_id}/season/{season_number}"
    params = {"api_key": api_key, "language": "zh-CN"}
    try:
        data = await _request(url, params, proxy)
        if data:
            return data.get("episodes", [])
    except Exception as e:
        raise Exception(f"获取 S{season_number} 剧集失败: {e}")
    return []


async def fetch_movie_details(tmdb_id: str, api_key: str, proxy: Optional[str] = None) -> Optional[Dict]:
    url = f"{TMDB_BASE}/movie/{tmdb_id}"
    params = {"api_key": api_key, "language": "zh-CN"}
    return await _request(url, params, proxy)


async def fetch_all_episodes(tmdb_id: str, api_key: str, proxy: Optional[str] = None) -> tuple:
    """
    获取所有季的剧集。
    返回 (episodes, errors)，即使某季失败也继续获取其他季。
    """
    details = await fetch_tv_details(tmdb_id, api_key, proxy)
    if not details:
        return [], ["获取 TV 详情失败"]
    all_episodes = []
    errors = []
    for season in details.get("seasons", []):
        sn = season.get("season_number", 0)
        if sn == 0:
            continue
        await asyncio.sleep(0.5)
        try:
            episodes = await fetch_season_episodes(tmdb_id, sn, api_key, proxy)
            for ep in episodes:
                ep["_season_number"] = sn
            all_episodes.extend(episodes)
        except Exception as e:
            errors.append(str(e))
    return all_episodes, errors


# ─── 剧集组划分 ─────────────────────────────────────────────

def build_episode_groups(all_episodes: List[Dict]) -> List[Dict]:
    """以 finale 为界划分剧集组"""
    if not all_episodes:
        return []

    sorted_eps = sorted(all_episodes, key=lambda e: (e.get("_season_number", 0), e.get("episode_number", 0)))

    groups = []
    current_group = []
    group_index = 1

    for ep in sorted_eps:
        current_group.append(ep)
        if ep.get("episode_type") == "finale":
            groups.append({
                "name": f"第 {group_index} 季",
                "order": group_index,
                "episodes": list(current_group),
            })
            current_group = []
            group_index += 1

    if current_group:
        groups.append({
            "name": f"第 {group_index} 季",
            "order": group_index,
            "episodes": list(current_group),
        })

    return groups


def groups_to_output(groups: List[Dict], tmdb_id: str) -> Dict:
    output_groups = []
    for g in groups:
        episodes = []
        for idx, ep in enumerate(g["episodes"]):
            episodes.append({
                "episode_number": ep.get("episode_number"),
                "season_number": ep.get("_season_number"),
                "order": idx,
            })
        first_ep = g["episodes"][0] if g["episodes"] else {}
        air_date = first_ep.get("air_date", "")
        output_groups.append({
            "name": g["name"],
            "air_date": air_date,
            "order": g["order"],
            "episodes": episodes,
        })
    return {
        "description": "",
        "groups": output_groups,
        "id": str(tmdb_id),
    }


# ─── 工作线程 ───────────────────────────────────────────────

class FetchWorker(QThread):
    info_ready = pyqtSignal(dict)
    episodes_ready = pyqtSignal(list)
    groups_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    warning = pyqtSignal(str)

    def __init__(self, tmdb_id: str, media_type: str, api_key: str, proxy: Optional[str] = None):
        super().__init__()
        self.tmdb_id = tmdb_id
        self.media_type = media_type
        self.api_key = api_key
        self.proxy = proxy

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if self.media_type == "tv":
                details = loop.run_until_complete(fetch_tv_details(self.tmdb_id, self.api_key, self.proxy))
                if not details:
                    self.error.emit(f"获取 TV 详情失败 (TMDB ID: {self.tmdb_id})，请检查 ID 和 API Key")
                    return
                self.info_ready.emit(details)

                all_eps, errors = loop.run_until_complete(fetch_all_episodes(self.tmdb_id, self.api_key, self.proxy))
                self.episodes_ready.emit(all_eps)

                groups = build_episode_groups(all_eps)
                self.groups_ready.emit(groups_to_output(groups, self.tmdb_id))

                if errors:
                    self.warning.emit("部分季获取失败:\n" + "\n".join(errors))

            elif self.media_type == "movie":
                details = loop.run_until_complete(fetch_movie_details(self.tmdb_id, self.api_key, self.proxy))
                if not details:
                    self.error.emit(f"获取电影详情失败 (TMDB ID: {self.tmdb_id})，请检查 ID 和 API Key")
                    return
                self.info_ready.emit(details)
                self.episodes_ready.emit([])
                self.groups_ready.emit({"id": str(self.tmdb_id), "description": "", "groups": []})
        except Exception as e:
            self.error.emit(str(e))
        finally:
            loop.close()


# ─── 主窗口 ─────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TMDB 剧集组生成器")
        self.setMinimumSize(1100, 750)
        self.worker = None
        self.settings = QSettings("TMDBEpisodeGroupTool", "Settings")
        self._show_name = ""
        self._tmdb_id = ""
        self._media_type = ""
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)

        # ── 配置区 ──
        config_group = QGroupBox("TMDB 配置")
        config_layout = QVBoxLayout(config_group)

        # API Key 行
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("填入你的 TMDB API Key")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(self.api_key_input)

        self.show_key_btn = QPushButton("显示")
        self.show_key_btn.setFixedWidth(60)
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self._toggle_key_visibility)
        key_row.addWidget(self.show_key_btn)
        config_layout.addLayout(key_row)

        # 代理行
        proxy_row = QHBoxLayout()
        self.proxy_check = QCheckBox("启用代理")
        proxy_row.addWidget(self.proxy_check)
        proxy_row.addWidget(QLabel("代理地址:"))
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("例如: http://127.0.0.1:7890")
        proxy_row.addWidget(self.proxy_input)
        config_layout.addLayout(proxy_row)

        main_layout.addWidget(config_group)

        # ── 查询区 ──
        query_group = QGroupBox("查询")
        query_layout = QHBoxLayout(query_group)

        query_layout.addWidget(QLabel("TMDB ID:"))
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("例如: 62104")
        self.id_input.setFixedWidth(150)
        query_layout.addWidget(self.id_input)

        query_layout.addWidget(QLabel("类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["tv", "movie"])
        self.type_combo.setFixedWidth(100)
        query_layout.addWidget(self.type_combo)

        self.fetch_btn = QPushButton("获取信息")
        self.fetch_btn.setFixedWidth(120)
        self.fetch_btn.clicked.connect(self._on_fetch)
        query_layout.addWidget(self.fetch_btn)

        query_layout.addStretch()
        main_layout.addWidget(query_group)

        # ── 内容区 ──
        self.tabs = QTabWidget()

        # Tab 1: 基本信息
        info_tab = QWidget()
        info_layout = QVBoxLayout(info_tab)
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setFont(QFont("Consolas", 10))
        info_layout.addWidget(self.info_text)
        self.tabs.addTab(info_tab, "基本信息")

        # Tab 2: 剧集列表
        eps_tab = QWidget()
        eps_layout = QVBoxLayout(eps_tab)
        self.eps_table = QTableWidget()
        self.eps_table.setColumnCount(7)
        self.eps_table.setHorizontalHeaderLabels(["TMDB季", "集号", "标题", "首播日期", "episode_type", "评分", "时长(分)"])
        self.eps_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.eps_table.horizontalHeader().setStretchLastSection(True)
        self.eps_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.eps_table.setAlternatingRowColors(True)
        eps_layout.addWidget(self.eps_table)
        self.tabs.addTab(eps_tab, "剧集列表")

        # Tab 3: 剧集组
        group_tab = QWidget()
        group_layout = QVBoxLayout(group_tab)
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Consolas", 10))
        group_layout.addWidget(self.result_text)

        copy_btn = QPushButton("复制剧集组 JSON")
        copy_btn.clicked.connect(self._on_copy)
        group_layout.addWidget(copy_btn)
        self.tabs.addTab(group_tab, "自动生成的剧集组")

        # Tab 4: 渲染词
        render_tab = QWidget()
        render_layout = QVBoxLayout(render_tab)
        self.render_text = QTextEdit()
        self.render_text.setReadOnly(True)
        self.render_text.setFont(QFont("Consolas", 10))
        render_layout.addWidget(self.render_text)

        copy_render_btn = QPushButton("复制渲染词")
        copy_render_btn.clicked.connect(self._on_copy_render)
        render_layout.addWidget(copy_render_btn)
        self.tabs.addTab(render_tab, "渲染词")

        main_layout.addWidget(self.tabs, 1)

        self.statusBar().showMessage("就绪")

        # 恢复上次保存的配置
        self._load_settings()

    def _toggle_key_visibility(self, checked: bool):
        self.api_key_input.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self.show_key_btn.setText("隐藏" if checked else "显示")

    def _load_settings(self):
        self.api_key_input.setText(self.settings.value("api_key", ""))
        self.proxy_check.setChecked(self.settings.value("proxy_enabled", False, type=bool))
        self.proxy_input.setText(self.settings.value("proxy_url", ""))

    def _save_settings(self):
        self.settings.setValue("api_key", self.api_key_input.text().strip())
        self.settings.setValue("proxy_enabled", self.proxy_check.isChecked())
        self.settings.setValue("proxy_url", self.proxy_input.text().strip())

    def _get_proxy(self) -> Optional[str]:
        if self.proxy_check.isChecked():
            url = self.proxy_input.text().strip()
            if url:
                return url
        return None

    def _on_fetch(self):
        tmdb_id = self.id_input.text().strip()
        media_type = self.type_combo.currentText()
        api_key = self.api_key_input.text().strip()

        if not tmdb_id:
            QMessageBox.warning(self, "提示", "请输入 TMDB ID")
            return
        if not api_key:
            QMessageBox.warning(self, "提示", "请填入 TMDB API Key")
            return

        self._save_settings()

        self.fetch_btn.setEnabled(False)
        self.info_text.clear()
        self.eps_table.setRowCount(0)
        self.result_text.clear()
        self.render_text.clear()
        self._tmdb_id = tmdb_id
        self._media_type = media_type
        self._show_name = ""
        self.statusBar().showMessage(f"正在获取 {media_type}/{tmdb_id} ...")

        self.worker = FetchWorker(tmdb_id, media_type, api_key, self._get_proxy())
        self.worker.info_ready.connect(self._on_info_ready)
        self.worker.episodes_ready.connect(self._on_episodes_ready)
        self.worker.groups_ready.connect(self._on_groups_ready)
        self.worker.error.connect(self._on_error)
        self.worker.warning.connect(self._on_warning)
        self.worker.finished.connect(lambda: self.fetch_btn.setEnabled(True))
        self.worker.start()

    def _on_info_ready(self, details: dict):
        media_type = self.type_combo.currentText()
        self._show_name = details.get("name", "") or details.get("title", "")
        lines = []
        if media_type == "tv":
            lines.append(f"标题: {details.get('name', 'N/A')}")
            lines.append(f"原始标题: {details.get('original_name', 'N/A')}")
            lines.append(f"首播日期: {details.get('first_air_date', 'N/A')}")
            lines.append(f"末播日期: {details.get('last_air_date', 'N/A')}")
            lines.append(f"状态: {details.get('status', 'N/A')}")
            lines.append(f"总季数: {details.get('number_of_seasons', 'N/A')}")
            lines.append(f"总集数: {details.get('number_of_episodes', 'N/A')}")
            lines.append(f"评分: {details.get('vote_average', 'N/A')}")
            genres = ", ".join(g.get("name", "") for g in details.get("genres", []))
            lines.append(f"类型: {genres}")
            lines.append(f"简介: {details.get('overview', 'N/A')[:200]}")
            seasons_info = []
            for s in details.get("seasons", []):
                if s.get("season_number", 0) > 0:
                    seasons_info.append(f"  S{s['season_number']}: {s.get('name', '')} ({s.get('episode_count', '?')}集)")
            if seasons_info:
                lines.append("季信息:\n" + "\n".join(seasons_info))
        else:
            lines.append(f"标题: {details.get('title', 'N/A')}")
            lines.append(f"原始标题: {details.get('original_title', 'N/A')}")
            lines.append(f"上映日期: {details.get('release_date', 'N/A')}")
            lines.append(f"评分: {details.get('vote_average', 'N/A')}")
            genres = ", ".join(g.get("name", "") for g in details.get("genres", []))
            lines.append(f"类型: {genres}")
            lines.append(f"简介: {details.get('overview', 'N/A')[:200]}")

        self.info_text.setPlainText("\n".join(lines))
        self.statusBar().showMessage("基本信息已获取")

    def _on_episodes_ready(self, episodes: list):
        self.eps_table.setRowCount(len(episodes))
        for row, ep in enumerate(episodes):
            sn = str(ep.get("_season_number", ep.get("season_number", "")))
            en = str(ep.get("episode_number", ""))
            name = ep.get("name", "")
            air = ep.get("air_date", "")
            ep_type = ep.get("episode_type", "standard")
            rating = str(ep.get("vote_average", ""))
            runtime = str(ep.get("runtime", ""))

            self.eps_table.setItem(row, 0, QTableWidgetItem(sn))
            self.eps_table.setItem(row, 1, QTableWidgetItem(en))
            self.eps_table.setItem(row, 2, QTableWidgetItem(name))
            self.eps_table.setItem(row, 3, QTableWidgetItem(air))

            type_item = QTableWidgetItem(ep_type)
            if ep_type == "finale":
                type_item.setBackground(QColor(255, 200, 200))
                type_item.setForeground(QColor(180, 0, 0))
            elif ep_type == "mid_season":
                type_item.setBackground(QColor(255, 240, 200))
                type_item.setForeground(QColor(180, 120, 0))
            self.eps_table.setItem(row, 4, type_item)

            self.eps_table.setItem(row, 5, QTableWidgetItem(rating))
            self.eps_table.setItem(row, 6, QTableWidgetItem(runtime))

        self.eps_table.resizeColumnsToContents()
        self.statusBar().showMessage(f"已加载 {len(episodes)} 集信息")

    def _on_groups_ready(self, output: dict):
        groups = output.get("groups", [])
        if not groups:
            self.result_text.setPlainText("（电影类型无剧集组）")
            return

        lines = []
        lines.append(f"共划分 {len(groups)} 个剧集组\n")

        for g in groups:
            name = g["name"]
            order = g["order"]
            eps = g["episodes"]
            lines.append(f"{'='*60}")
            lines.append(f"  {name} (order={order}) — 共 {len(eps)} 集")

            tmdb_seasons = sorted(set(e.get("season_number", 0) for e in eps))
            for ts in tmdb_seasons:
                season_eps = [e for e in eps if e.get("season_number", 0) == ts]
                ep_nums = [e.get("episode_number", 0) for e in season_eps]
                if not ep_nums:
                    continue
                min_ep, max_ep = min(ep_nums), max(ep_nums)

                if min_ep == max_ep:
                    lines.append(f"    TMDB S{ts}: E{min_ep}")
                else:
                    lines.append(f"    TMDB S{ts}: E{min_ep}-E{max_ep}")

            lines.append("")

        lines.append(f"{'='*60}")
        lines.append("完整 JSON 输出:\n")
        lines.append(json.dumps(output, ensure_ascii=False, indent=2))

        self.result_text.setPlainText("\n".join(lines))
        self.statusBar().showMessage(f"剧集组已生成: {len(groups)} 个组")

        # 生成渲染词
        self._generate_render_words(output)

    def _generate_render_words(self, output: dict):
        groups = output.get("groups", [])
        tmdb_id = output.get("id", "")
        if not groups or len(groups) <= 1:
            self.render_text.setPlainText("（仅1个组，无需渲染词）")
            return

        lines = []
        if self._show_name:
            lines.append(f"#{self._show_name}")

        # 计算每组之前所有组的累计集数
        cumulative = 0
        for i, g in enumerate(groups):
            eps = g["episodes"]
            if not eps:
                continue
            ep_nums = [e.get("episode_number", 0) for e in eps]
            min_ep, max_ep = min(ep_nums), max(ep_nums)
            order = g["order"]

            # 第一组不需要渲染词（1:1默认映射）
            if i == 0:
                cumulative += len(eps)
                continue

            lines.append(
                f"@?{{[tmdbid={tmdb_id};type={self._media_type};e={min_ep}-{max_ep}]}} "
                f"=> {{[s={order};e=EP-{cumulative}]}}"
            )
            cumulative += len(eps)

        self.render_text.setPlainText("\n".join(lines))

    def _on_error(self, msg: str):
        self.statusBar().showMessage(f"错误: {msg}")
        QMessageBox.critical(self, "错误", msg)

    def _on_warning(self, msg: str):
        self.statusBar().showMessage(f"警告: {msg}")
        QMessageBox.warning(self, "部分失败", msg + "\n\n已获取的数据仍会显示，但可能不完整。")

    def _on_copy(self):
        text = self.result_text.toPlainText()
        json_marker = "完整 JSON 输出:\n"
        idx = text.find(json_marker)
        json_text = text[idx + len(json_marker):] if idx >= 0 else text
        QApplication.clipboard().setText(json_text)
        self.statusBar().showMessage("已复制剧集组 JSON 到剪贴板")

    def _on_copy_render(self):
        text = self.render_text.toPlainText()
        QApplication.clipboard().setText(text)
        self.statusBar().showMessage("已复制渲染词到剪贴板")

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    app.setStyleSheet("""
        QMainWindow { background: #f5f5f5; }
        QGroupBox { font-weight: bold; border: 1px solid #ccc; border-radius: 4px; margin-top: 8px; padding-top: 16px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        QPushButton { padding: 6px 16px; border-radius: 4px; }
        QPushButton:hover { background: #e0e0e0; }
        QTableWidget { gridline-color: #ddd; }
        QTextEdit { border: 1px solid #ccc; border-radius: 4px; }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
