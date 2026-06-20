#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Anime Manager ED2K 哈希搜索客户端
调用后端 /api/file_hashes 接口，支持关键字、TMDB ID、类型、季号筛选。
配置存储使用 QSettings（Windows 注册表 / Linux ~/.config），不生成外部配置文件。
"""

import json
import sys
import os
import traceback
from urllib.parse import urljoin

import requests

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QSpinBox,
    QProgressBar, QGroupBox, QFormLayout, QMenu, QDialog,
    QDialogButtonBox, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QAction, QFont


DEFAULT_COLUMNS = [
    "id", "sha1", "ed2k", "ed2k_link", "original_filename", "file_size",
    "tmdb_id", "title", "season", "episode", "media_type", "resolution",
    "team", "video_encode", "source_path", "target_path", "calculated_at"
]


class SearchThread(QThread):
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, base_url, token, params):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.params = params

    def run(self):
        try:
            url = urljoin(self.base_url + "/", "api/file_hashes")
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            resp = requests.get(url, headers=headers, params=self.params, timeout=30)
            resp.raise_for_status()
            self.result_ready.emit(resp.json())
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("无法连接到 API，请检查 Base URL 和网络。")
        except requests.exceptions.HTTPError as e:
            try:
                detail = e.response.json().get("detail", e.response.text)
            except Exception:
                detail = e.response.text
            self.error_occurred.emit(f"HTTP {e.response.status_code}: {detail}")
        except Exception as e:
            self.error_occurred.emit(f"请求失败: {str(e)}")


class SettingsDialog(QDialog):
    def __init__(self, base_url, token, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
        self.resize(500, 200)

        layout = QFormLayout(self)

        self.base_url_input = QLineEdit(base_url)
        self.base_url_input.setPlaceholderText("http://127.0.0.1:8000")
        layout.addRow("API Base URL:", self.base_url_input)

        self.token_input = QTextEdit(token)
        self.token_input.setPlaceholderText("登录后获取的 JWT Token")
        self.token_input.setMaximumHeight(80)
        layout.addRow("JWT Token:", self.token_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_settings(self):
        return {
            "base_url": self.base_url_input.text().strip(),
            "token": self.token_input.toPlainText().strip(),
        }


class Ed2kSearchWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anime Manager - ED2K 哈希搜索")
        self.setMinimumSize(1400, 800)

        self.settings = QSettings("AnimeManager", "Ed2kSearch")
        self.current_total = 0
        self.current_offset = 0
        self.current_params = {}
        self.search_thread = None

        self._build_ui()
        self._restore_last_search()

    def _get(self, key, default=""):
        return self.settings.value(key, default)

    def _set(self, key, value):
        self.settings.setValue(key, value)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # 标题
        title_label = QLabel("Anime Manager - ED2K 哈希搜索")
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # 设置按钮
        setting_bar = QHBoxLayout()
        self.setting_btn = QPushButton("⚙️ 设置")
        self.setting_btn.setFixedWidth(100)
        self.setting_btn.clicked.connect(self.open_settings)
        setting_bar.addWidget(self.setting_btn)
        setting_bar.addStretch()
        main_layout.addLayout(setting_bar)

        # 搜索条件
        search_group = QGroupBox("搜索条件")
        search_layout = QFormLayout(search_group)

        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("关键字：文件名 / 标题 / ED2K / SHA1 / 路径")
        self.keyword_input.returnPressed.connect(self.do_search_first)
        search_layout.addRow("关键字:", self.keyword_input)

        filter_row = QHBoxLayout()
        self.tmdb_input = QLineEdit()
        self.tmdb_input.setPlaceholderText("TMDB ID")
        self.tmdb_input.setFixedWidth(160)
        self.tmdb_input.returnPressed.connect(self.do_search_first)

        self.type_combo = QComboBox()
        self.type_combo.addItem("全部", "")
        self.type_combo.addItem("TV", "tv")
        self.type_combo.addItem("Movie", "movie")
        self.type_combo.setFixedWidth(120)

        self.season_input = QSpinBox()
        self.season_input.setMinimum(0)
        self.season_input.setMaximum(9999)
        self.season_input.setSpecialValueText("不限")
        self.season_input.setFixedWidth(100)

        self.limit_input = QSpinBox()
        self.limit_input.setMinimum(1)
        self.limit_input.setMaximum(500)
        self.limit_input.setValue(50)
        self.limit_input.setFixedWidth(100)

        filter_row.addWidget(QLabel("TMDB ID:"))
        filter_row.addWidget(self.tmdb_input)
        filter_row.addSpacing(16)
        filter_row.addWidget(QLabel("类型:"))
        filter_row.addWidget(self.type_combo)
        filter_row.addSpacing(16)
        filter_row.addWidget(QLabel("季号:"))
        filter_row.addWidget(self.season_input)
        filter_row.addSpacing(16)
        filter_row.addWidget(QLabel("每页:"))
        filter_row.addWidget(self.limit_input)
        filter_row.addStretch()
        search_layout.addRow(filter_row)

        btn_row = QHBoxLayout()
        self.search_btn = QPushButton("🔍 搜索")
        self.search_btn.setFixedWidth(120)
        self.search_btn.clicked.connect(self.do_search_first)
        self.reset_btn = QPushButton("重置")
        self.reset_btn.setFixedWidth(100)
        self.reset_btn.clicked.connect(self.reset_filters)
        btn_row.addWidget(self.search_btn)
        btn_row.addWidget(self.reset_btn)
        btn_row.addStretch()
        search_layout.addRow(btn_row)

        main_layout.addWidget(search_group)

        # 状态条
        status_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(200)
        self.progress.setVisible(False)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.progress)
        main_layout.addLayout(status_layout)

        # 结果表格
        self.table = QTableWidget()
        self.table.setColumnCount(len(DEFAULT_COLUMNS))
        self.table.setHorizontalHeaderLabels(DEFAULT_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_menu)
        self.table.setAlternatingRowColors(True)
        main_layout.addWidget(self.table)

        # 分页
        pager = QHBoxLayout()
        self.first_btn = QPushButton("首页")
        self.first_btn.clicked.connect(self.go_first)
        self.prev_btn = QPushButton("上一页")
        self.prev_btn.clicked.connect(self.go_prev)
        self.next_btn = QPushButton("下一页")
        self.next_btn.clicked.connect(self.go_next)
        self.page_label = QLabel("第 0 / 0 页 (共 0 条)")

        pager.addWidget(self.first_btn)
        pager.addWidget(self.prev_btn)
        pager.addWidget(self.page_label)
        pager.addWidget(self.next_btn)
        pager.addStretch()
        main_layout.addLayout(pager)

        self.update_pager()

    def _restore_last_search(self):
        """恢复上次搜索条件"""
        self.keyword_input.setText(self._get("last_keyword", ""))
        self.tmdb_input.setText(self._get("last_tmdb_id", ""))

        media_type = self._get("last_media_type", "")
        index = 0
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == media_type:
                index = i
                break
        self.type_combo.setCurrentIndex(index)

        self.season_input.setValue(int(self._get("last_season", 0)))
        self.limit_input.setValue(int(self._get("last_limit", 50)))

        width = int(self._get("window_width", 1400))
        height = int(self._get("window_height", 800))
        self.resize(width, height)

    def _save_last_search(self):
        """保存当前搜索条件"""
        self._set("last_keyword", self.keyword_input.text().strip())
        self._set("last_tmdb_id", self.tmdb_input.text().strip())
        self._set("last_media_type", self.type_combo.currentData() or "")
        self._set("last_season", self.season_input.value())
        self._set("last_limit", self.limit_input.value())
        self.settings.sync()

    def closeEvent(self, event):
        """关闭时保存窗口尺寸"""
        self._set("window_width", self.width())
        self._set("window_height", self.height())
        self._save_last_search()
        event.accept()

    def open_settings(self):
        dlg = SettingsDialog(self._get("base_url", "http://127.0.0.1:8000"), self._get("token", ""), self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            settings = dlg.get_settings()
            self._set("base_url", settings["base_url"])
            self._set("token", settings["token"])
            self.settings.sync()

    def reset_filters(self):
        self.keyword_input.clear()
        self.tmdb_input.clear()
        self.type_combo.setCurrentIndex(0)
        self.season_input.setValue(0)
        self.limit_input.setValue(50)
        self._save_last_search()

    def get_search_params(self, offset=0):
        params = {
            "limit": self.limit_input.value(),
            "offset": offset,
        }
        q = self.keyword_input.text().strip()
        if q:
            params["q"] = q
        tmdb_id = self.tmdb_input.text().strip()
        if tmdb_id:
            params["tmdb_id"] = tmdb_id
        media_type = self.type_combo.currentData()
        if media_type:
            params["media_type"] = media_type
        season = self.season_input.value()
        if season > 0:
            params["season"] = season
        return params

    def do_search_first(self):
        params = self.get_search_params(0)
        self._save_last_search()
        self.run_search(params)

    def go_first(self):
        params = self.get_search_params(0)
        self._save_last_search()
        self.run_search(params)

    def go_prev(self):
        if self.current_offset - self.limit_input.value() < 0:
            return
        new_offset = self.current_offset - self.limit_input.value()
        params = self.get_search_params(new_offset)
        self._save_last_search()
        self.run_search(params)

    def go_next(self):
        if self.current_offset + self.limit_input.value() >= self.current_total:
            return
        new_offset = self.current_offset + self.limit_input.value()
        params = self.get_search_params(new_offset)
        self._save_last_search()
        self.run_search(params)

    def run_search(self, params):
        base_url = self._get("base_url", "").strip()
        if not base_url:
            QMessageBox.warning(self, "缺少配置", "请先点击右上角 ⚙️ 设置 API Base URL 和 Token")
            return

        self.current_params = params
        self.search_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("搜索中...")

        self.search_thread = SearchThread(
            base_url,
            self._get("token", ""),
            params
        )
        self.search_thread.result_ready.connect(self.handle_result)
        self.search_thread.error_occurred.connect(self.handle_error)
        self.search_thread.finished.connect(self.search_finished)
        self.search_thread.start()

    def handle_result(self, data):
        self.current_total = data.get("total", 0)
        self.current_offset = data.get("offset", 0)
        items = data.get("data", [])

        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            for col, key in enumerate(DEFAULT_COLUMNS):
                val = item.get(key)
                if val is None:
                    val = ""
                cell = QTableWidgetItem(str(val))
                cell.setData(Qt.ItemDataRole.UserRole, str(val))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, cell)

        self.table.resizeColumnsToContents()
        self.update_pager()
        self.status_label.setText(f"返回 {len(items)} 条，共 {self.current_total} 条")

    def handle_error(self, msg):
        QMessageBox.critical(self, "请求错误", msg)
        self.table.setRowCount(0)
        self.current_total = 0
        self.current_offset = 0
        self.update_pager()
        self.status_label.setText("请求失败")

    def search_finished(self):
        self.search_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)

    def update_pager(self):
        limit = self.limit_input.value()
        total_pages = (self.current_total + limit - 1) // limit if limit else 0
        current_page = (self.current_offset // limit) + 1 if limit else 0
        self.page_label.setText(f"第 {current_page} / {total_pages} 页 (共 {self.current_total} 条)")
        self.prev_btn.setEnabled(self.current_offset > 0)
        self.next_btn.setEnabled(self.current_offset + limit < self.current_total)

    def show_table_menu(self, position):
        item = self.table.itemAt(position)
        if not item:
            return

        menu = QMenu()
        copy_cell_action = QAction("复制单元格", self)
        copy_row_action = QAction("复制整行 (JSON)", self)
        copy_ed2k_action = QAction("复制 ED2K 链接", self)

        copy_cell_action.triggered.connect(lambda: self.copy_cell(item))
        copy_row_action.triggered.connect(lambda: self.copy_row(item.row()))
        copy_ed2k_action.triggered.connect(lambda: self.copy_ed2k(item.row()))

        menu.addAction(copy_cell_action)
        menu.addAction(copy_row_action)
        menu.addAction(copy_ed2k_action)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def copy_cell(self, item):
        QApplication.clipboard().setText(item.text())

    def copy_row(self, row):
        row_data = {}
        for col, key in enumerate(DEFAULT_COLUMNS):
            item = self.table.item(row, col)
            row_data[key] = item.text() if item else ""
        QApplication.clipboard().setText(json.dumps(row_data, ensure_ascii=False, indent=2))

    def copy_ed2k(self, row):
        col = DEFAULT_COLUMNS.index("ed2k_link")
        item = self.table.item(row, col)
        if item and item.text():
            QApplication.clipboard().setText(item.text())


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = Ed2kSearchWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_msg = f"程序启动失败:\n{str(e)}\n\n{traceback.format_exc()}"
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ed2k_search_client_error.log")
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(error_msg)
        except Exception:
            pass

        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            _app = QApplication(sys.argv)
            QMessageBox.critical(None, "启动错误", error_msg)
        except Exception:
            pass
        sys.exit(1)
