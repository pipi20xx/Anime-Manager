
# -*- coding: utf-8 -*-
"""
STRM 文件路径替换工具 (PyQt6)

功能：
  - 选择一个文件夹，递归查找所有层级中的 .strm 文件
  - 自定义多组"替换为"规则
  - 三大页面：① 配置页 ② 预览结果页 ③ 处理日志页
  - 支持备份原文件，可自定义备份文件夹（保持目录结构）
  - 支持仅替换路径 / 全文替换两种模式
  - 窗口宽高可任意调整

依赖安装：
  pip install PyQt6

运行：
  python strm_replacer.py
"""

import sys
import os
import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QProgressBar, QMessageBox, QGroupBox, QRadioButton, QButtonGroup,
    QTabWidget, QScrollArea
)


# ──────────────────────────────────────────────
# 后台处理线程
# ──────────────────────────────────────────────
class StrmReplaceWorker(QThread):
    """
    后台线程：递归遍历文件夹，对 .strm 文件执行文字替换。
    """
    progress = pyqtSignal(int, int)          # current, total
    log = pyqtSignal(str)                      # 日志信息
    finished_signal = pyqtSignal(int, int)     # 成功数, 失败数

    def __init__(self, folder: str, rules: list, backup: bool, mode: str,
                 backup_dir: str = ""):
        super().__init__()
        self.folder = folder
        self.rules = rules          # [(old, new), ...]
        self.backup = backup
        self.mode = mode            # "path" 或 "full"
        self.backup_dir = backup_dir  # 备份目标文件夹，空字符串=同目录 .bak

    def run(self):
        folder_path = Path(self.folder)
        # 递归收集所有 .strm 文件
        strm_files = list(folder_path.rglob("*.strm"))
        total = len(strm_files)
        success = 0
        fail = 0

        self.log.emit(f"找到 {total} 个 .strm 文件，开始处理...\n")
        self.progress.emit(0, total)

        for i, strm_file in enumerate(strm_files, 1):
            try:
                # 读取文件内容
                content = strm_file.read_text(encoding="utf-8")
                original_content = content

                if self.mode == "path":
                    # 仅替换路径部分（取每行中类似路径的内容）
                    lines = content.splitlines()
                    new_lines = []
                    for line in lines:
                        line_stripped = line.strip()
                        # 如果这一行看起来像一个路径（包含 / 或 \）
                        if "/" in line_stripped or "\\" in line_stripped:
                            for old, new in self.rules:
                                line = line.replace(old, new)
                        new_lines.append(line)
                    new_content = "\n".join(new_lines)
                    # 保持文件末尾换行
                    if content.endswith("\n") and not new_content.endswith("\n"):
                        new_content += "\n"
                else:
                    # 全文替换：对所有内容执行替换
                    for old, new in self.rules:
                        content = content.replace(old, new)
                    new_content = content

                if new_content != original_content:
                    # 备份
                    if self.backup:
                        if self.backup_dir:
                            # 备份到指定文件夹，保持相对目录结构
                            rel = strm_file.relative_to(folder_path)
                            backup_path = Path(self.backup_dir) / rel
                            backup_path.parent.mkdir(parents=True, exist_ok=True)
                        else:
                            # 默认：同目录 .bak 文件
                            backup_path = strm_file.with_suffix(strm_file.suffix + ".bak")
                        if not backup_path.exists():
                            shutil.copy2(strm_file, backup_path)

                    # 写入
                    strm_file.write_text(new_content, encoding="utf-8")
                    success += 1
                    self.log.emit(f"  [已替换] {strm_file.relative_to(folder_path)}")
                else:
                    self.log.emit(f"  [无变化] {strm_file.relative_to(folder_path)}")

            except Exception as e:
                fail += 1
                self.log.emit(f"  [错误]   {strm_file} -> {e}")

            self.progress.emit(i, total)

        self.log.emit(f"\n处理完成！成功替换: {success}，失败: {fail}，总计: {total}\n")
        self.finished_signal.emit(success, fail)


# ──────────────────────────────────────────────
# 主窗口
# ──────────────────────────────────────────────
class StrmReplacerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("STRM 路径替换工具")
        self.resize(1000, 750)
        # 只设置最小尺寸，允许任意调整宽高
        self.setMinimumSize(600, 400)
        self.worker = None
        self.preview_data = []

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # ============================================================
        # 最外层三大 Tab 页面
        # ============================================================
        self.main_tabs = QTabWidget()

        # ── Tab 1: 配置页 ──
        config_page = QWidget()
        config_layout = QVBoxLayout(config_page)
        config_layout.setSpacing(8)
        config_layout.setContentsMargins(12, 12, 12, 12)

        # 用 QScrollArea 包裹，内容超出时可滚动
        config_scroll = QScrollArea()
        config_scroll.setWidgetResizable(True)
        config_scroll_content = QWidget()
        config_scroll_layout = QVBoxLayout(config_scroll_content)
        config_scroll_layout.setSpacing(8)
        config_scroll_layout.setContentsMargins(0, 0, 0, 0)

        # ====== 文件夹选择 ======
        folder_group = QGroupBox("① 选择文件夹")
        folder_layout = QHBoxLayout(folder_group)
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("点击右侧按钮选择包含 .strm 文件的文件夹...")
        self.folder_edit.setReadOnly(True)
        btn_browse = QPushButton("浏览...")
        btn_browse.setFixedWidth(100)
        btn_browse.clicked.connect(self._on_browse)
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(btn_browse)
        config_scroll_layout.addWidget(folder_group)

        # ====== 替换规则 ======
        rules_group = QGroupBox("② 设置替换规则（可添加多组）")
        rules_layout = QVBoxLayout(rules_group)

        # 表格
        self.rules_table = QTableWidget(0, 3)
        self.rules_table.setHorizontalHeaderLabels(["序号", "查找内容（原路径片段）", "替换为（新路径片段）"])
        self.rules_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.rules_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.rules_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.rules_table.setColumnWidth(0, 60)
        self.rules_table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rules_table.setMaximumHeight(180)
        rules_layout.addWidget(self.rules_table)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ 添加规则")
        btn_add.setFixedWidth(120)
        btn_add.clicked.connect(self._add_rule)
        btn_del = QPushButton("- 删除选中规则")
        btn_del.setFixedWidth(140)
        btn_del.clicked.connect(self._del_rule)
        btn_clear = QPushButton("清空规则")
        btn_clear.setFixedWidth(100)
        btn_clear.clicked.connect(self._clear_rules)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        rules_layout.addLayout(btn_row)

        # 替换模式
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("替换模式:"))
        self.rb_path = QRadioButton("仅替换路径行（推荐）")
        self.rb_path.setChecked(True)
        self.rb_full = QRadioButton("全文替换")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_path)
        self.mode_group.addButton(self.rb_full)
        mode_row.addWidget(self.rb_path)
        mode_row.addWidget(self.rb_full)
        mode_row.addStretch()
        rules_layout.addLayout(mode_row)

        # 备份选项
        backup_row = QHBoxLayout()
        self.cb_backup = QCheckBox("替换前自动备份原文件")
        self.cb_backup.setChecked(True)
        self.cb_backup.toggled.connect(self._on_backup_toggled)
        backup_row.addWidget(self.cb_backup)
        backup_row.addSpacing(20)

        self.backup_dir_label = QLabel("备份到文件夹:")
        backup_row.addWidget(self.backup_dir_label)
        self.backup_dir_edit = QLineEdit()
        self.backup_dir_edit.setPlaceholderText("留空 = 在原文件旁生成 .strm.bak；选择文件夹 = 保持目录结构备份到该文件夹")
        self.backup_dir_edit.setReadOnly(True)
        backup_row.addWidget(self.backup_dir_edit, 1)
        self.btn_backup_browse = QPushButton("浏览...")
        self.btn_backup_browse.setFixedWidth(100)
        self.btn_backup_browse.clicked.connect(self._on_backup_browse)
        backup_row.addWidget(self.btn_backup_browse)
        self.btn_backup_clear = QPushButton("清除")
        self.btn_backup_clear.setFixedWidth(60)
        self.btn_backup_clear.clicked.connect(lambda: self.backup_dir_edit.clear())
        backup_row.addWidget(self.btn_backup_clear)

        rules_layout.addLayout(backup_row)

        config_scroll_layout.addWidget(rules_group)

        # ====== 操作按钮 ======
        action_row = QHBoxLayout()
        self.btn_preview = QPushButton("👁  预览替换效果")
        self.btn_preview.setFixedHeight(38)
        self.btn_preview.clicked.connect(self._on_preview)
        self.btn_run = QPushButton("🚀  开始替换")
        self.btn_run.setFixedHeight(38)
        self.btn_run.setStyleSheet("QPushButton { font-weight: bold; font-size: 14px; }")
        self.btn_run.clicked.connect(self._on_run)
        action_row.addWidget(self.btn_preview)
        action_row.addWidget(self.btn_run)
        config_scroll_layout.addLayout(action_row)

        # ====== 进度条 ======
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setVisible(False)
        config_scroll_layout.addWidget(self.progress_bar)

        # 弹簧，让内容顶部对齐
        config_scroll_layout.addStretch()

        config_scroll.setWidget(config_scroll_content)
        config_layout.addWidget(config_scroll)
        self.main_tabs.addTab(config_page, "⚙ 配置")

        # ── Tab 2: 预览结果页 ──
        preview_page = QWidget()
        preview_layout = QVBoxLayout(preview_page)
        preview_layout.setSpacing(6)
        preview_layout.setContentsMargins(12, 12, 12, 12)

        self.preview_label = QLabel("📋 预览结果（仅显示有变化的文件，支持滚动浏览全部记录）")
        preview_layout.addWidget(self.preview_label)

        self.preview_table = QTableWidget(0, 4)
        self.preview_table.setHorizontalHeaderLabels(["序号", "文件路径", "替换前", "替换后"])
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.preview_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.preview_table.setColumnWidth(0, 50)
        self.preview_table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.preview_table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.preview_table.setAlternatingRowColors(True)
        preview_layout.addWidget(self.preview_table)

        self.main_tabs.addTab(preview_page, "👁 预览结果")

        # ── Tab 3: 处理日志页 ──
        log_page = QWidget()
        log_layout = QVBoxLayout(log_page)
        log_layout.setSpacing(6)
        log_layout.setContentsMargins(12, 12, 12, 12)

        log_top_row = QHBoxLayout()
        log_top_row.addWidget(QLabel("📝 处理日志:"))
        btn_clear_log = QPushButton("清空日志")
        btn_clear_log.setFixedWidth(100)
        btn_clear_log.clicked.connect(lambda: self.log_text.clear())
        log_top_row.addStretch()
        log_top_row.addWidget(btn_clear_log)
        log_layout.addLayout(log_top_row)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        self.main_tabs.addTab(log_page, "📝 处理日志")

        # 添加到主布局
        main_layout.addWidget(self.main_tabs)

        # 默认添加一行规则
        self._add_rule()

    # ── 文件夹选择 ──
    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(self, "选择包含 .strm 文件的文件夹")
        if folder:
            self.folder_edit.setText(folder)

    # ── 备份文件夹选择 ──
    def _on_backup_toggled(self, checked):
        """备份勾选框状态变化时，启用/禁用相关控件"""
        self.backup_dir_label.setEnabled(checked)
        self.backup_dir_edit.setEnabled(checked)
        self.btn_backup_browse.setEnabled(checked)
        self.btn_backup_clear.setEnabled(checked)

    def _on_backup_browse(self):
        folder = QFileDialog.getExistingDirectory(self, "选择备份文件夹")
        if folder:
            self.backup_dir_edit.setText(folder)

    # ── 规则管理 ──
    def _add_rule(self, old_text="", new_text=""):
        row = self.rules_table.rowCount()
        self.rules_table.insertRow(row)
        self.rules_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.rules_table.setItem(row, 1, QTableWidgetItem(old_text))
        self.rules_table.setItem(row, 2, QTableWidgetItem(new_text))
        item = self.rules_table.item(row, 0)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _del_rule(self):
        rows = sorted(set(idx.row() for idx in self.rules_table.selectedIndexes()), reverse=True)
        if not rows:
            QMessageBox.information(self, "提示", "请先在表格中选中要删除的行。")
            return
        for r in rows:
            self.rules_table.removeRow(r)
        for i in range(self.rules_table.rowCount()):
            self.rules_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            item = self.rules_table.item(i, 0)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _clear_rules(self):
        self.rules_table.setRowCount(0)

    # ── 获取规则 ──
    def _get_rules(self):
        rules = []
        for row in range(self.rules_table.rowCount()):
            old_item = self.rules_table.item(row, 1)
            new_item = self.rules_table.item(row, 2)
            old_text = old_item.text() if old_item else ""
            new_text = new_item.text() if new_item else ""
            if old_text:
                rules.append((old_text, new_text))
        return rules

    # ── 验证输入 ──
    def _validate(self):
        folder = self.folder_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "警告", "请先选择一个有效的文件夹。")
            return False
        rules = self._get_rules()
        if not rules:
            QMessageBox.warning(self, "警告", "请至少添加一条有效的替换规则（查找内容不能为空）。")
            return False
        return True

    # ── 预览 ──
    def _on_preview(self):
        if not self._validate():
            return

        folder = self.folder_edit.text().strip()
        rules = self._get_rules()
        mode = "path" if self.rb_path.isChecked() else "full"

        folder_path = Path(folder)
        strm_files = list(folder_path.rglob("*.strm"))
        total = len(strm_files)

        if total == 0:
            QMessageBox.information(self, "提示", "所选文件夹中没有找到任何 .strm 文件。")
            return

        self.log_text.append(f"🔍 正在扫描 {total} 个 .strm 文件...\n")

        self.preview_data.clear()
        changed_count = 0

        for strm_file in strm_files:
            try:
                content = strm_file.read_text(encoding="utf-8")
                original_content = content

                if mode == "path":
                    lines = content.splitlines()
                    new_lines = []
                    for line in lines:
                        line_stripped = line.strip()
                        if "/" in line_stripped or "\\" in line_stripped:
                            for old, new in rules:
                                line = line.replace(old, new)
                        new_lines.append(line)
                    new_content = "\n".join(new_lines)
                    if content.endswith("\n") and not new_content.endswith("\n"):
                        new_content += "\n"
                else:
                    for old, new in rules:
                        content = content.replace(old, new)
                    new_content = content

                if new_content != original_content:
                    rel_path = str(strm_file.relative_to(folder_path))
                    old_line = next((l for l in original_content.splitlines() if l.strip()), "")
                    new_line = next((l for l in new_content.splitlines() if l.strip()), "")
                    self.preview_data.append((rel_path, old_line, new_line))
                    changed_count += 1
            except Exception:
                pass

        # 填充预览表格
        self.preview_table.setRowCount(0)
        for idx, (rel_path, old_line, new_line) in enumerate(self.preview_data, 1):
            row = self.preview_table.rowCount()
            self.preview_table.insertRow(row)
            num_item = QTableWidgetItem(str(idx))
            num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_table.setItem(row, 0, num_item)
            self.preview_table.setItem(row, 1, QTableWidgetItem(rel_path))
            self.preview_table.setItem(row, 2, QTableWidgetItem(old_line))
            self.preview_table.setItem(row, 3, QTableWidgetItem(new_line))

        self.log_text.append(f"📋 预览完成：共 {total} 个文件，其中 {changed_count} 个将被修改。\n")

        # 自动切换到预览页
        self.main_tabs.setCurrentIndex(1)

    # ── 执行替换 ──
    def _on_run(self):
        if not self._validate():
            return

        folder = self.folder_edit.text().strip()
        rules = self._get_rules()
        backup = self.cb_backup.isChecked()
        backup_dir = self.backup_dir_edit.text().strip()
        mode = "path" if self.rb_path.isChecked() else "full"

        msg = f"即将对以下文件夹中的所有 .strm 文件执行替换：\n\n  {folder}\n\n"
        msg += f"替换规则数: {len(rules)}\n"
        msg += f"替换模式: {'仅替换路径行' if mode == 'path' else '全文替换'}\n"
        if backup:
            if backup_dir:
                msg += f"自动备份: 是（备份到 {backup_dir}，保持目录结构）\n"
            else:
                msg += "自动备份: 是（在原文件旁生成 .strm.bak）\n"
        else:
            msg += "自动备份: 否\n"
        msg += "\n确定要继续吗？"
        reply = QMessageBox.question(self, "确认", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.btn_run.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_text.clear()

        # 自动切换到日志页
        self.main_tabs.setCurrentIndex(2)

        self.worker = StrmReplaceWorker(folder, rules, backup, mode, backup_dir)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._on_log)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, current, total):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)

    def _on_log(self, msg):
        self.log_text.append(msg)

    def _on_finished(self, success, fail):
        self.btn_run.setEnabled(True)
        self.btn_preview.setEnabled(True)
        self.log_text.append(f"✅ 全部完成！成功: {success}，失败: {fail}")


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = StrmReplacerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
