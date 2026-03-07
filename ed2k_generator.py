import sys
import os
import hashlib
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton, QFileDialog, QProgressBar, 
    QGroupBox, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont


BLOCK_SIZE = 9728000


def md4_hash(data: bytes) -> bytes:
    return hashlib.new('md4', data).digest()


def calculate_hashes(file_path: str, progress_callback=None) -> tuple:
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    
    sha1_hash = hashlib.sha1()
    
    if file_size == 0:
        return file_name, file_size, md4_hash(b'').hex(), sha1_hash.hexdigest()
    
    if file_size < BLOCK_SIZE:
        with open(file_path, 'rb') as f:
            data = f.read()
        sha1_hash.update(data)
        return file_name, file_size, md4_hash(data).hex(), sha1_hash.hexdigest()
    
    block_hashes = b''
    total_blocks = (file_size + BLOCK_SIZE - 1) // BLOCK_SIZE
    blocks_processed = 0
    
    with open(file_path, 'rb') as f:
        while True:
            block = f.read(BLOCK_SIZE)
            if not block:
                break
            block_hashes += md4_hash(block)
            sha1_hash.update(block)
            blocks_processed += 1
            if progress_callback:
                progress_callback(int(blocks_processed / total_blocks * 100))
    
    final_hash = md4_hash(block_hashes).hex()
    return file_name, file_size, final_hash, sha1_hash.hexdigest()


def generate_ed2k_link(file_name: str, file_size: int, file_hash: str) -> str:
    return f"ed2k://|file|{file_name}|{file_size}|{file_hash}|/"


class HashWorker(QThread):
    progress = pyqtSignal(int, int, int)
    finished_single = pyqtSignal(str, int, str, str)
    finished_all = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, file_paths: list):
        super().__init__()
        self.file_paths = file_paths
        self._is_running = True
    
    def stop(self):
        self._is_running = False
    
    def run(self):
        total_files = len(self.file_paths)
        for idx, file_path in enumerate(self.file_paths):
            if not self._is_running:
                break
            try:
                file_name, file_size, ed2k_hash, sha1_hash = calculate_hashes(
                    file_path, 
                    lambda p: self.progress.emit(p, idx + 1, total_files)
                )
                self.finished_single.emit(file_name, file_size, ed2k_hash, sha1_hash)
            except Exception as e:
                self.error.emit(f"{os.path.basename(file_path)}: {str(e)}")
        self.finished_all.emit()


class DropLabel(QLabel):
    files_dropped = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(120)
        self.setText("📁 拖拽文件到此处\n或点击下方按钮选择文件")
        self.setStyleSheet("""
            QLabel {
                border: 3px dashed #aaa;
                border-radius: 10px;
                background-color: #f5f5f5;
                font-size: 16px;
                color: #666;
            }
            QLabel:hover {
                border-color: #4a90d9;
                background-color: #e8f4fc;
            }
        """)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QLabel {
                    border: 3px dashed #4a90d9;
                    border-radius: 10px;
                    background-color: #d0e8f8;
                    font-size: 16px;
                    color: #333;
                }
            """)
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QLabel {
                border: 3px dashed #aaa;
                border-radius: 10px;
                background-color: #f5f5f5;
                font-size: 16px;
                color: #666;
            }
            QLabel:hover {
                border-color: #4a90d9;
                background-color: #e8f4fc;
            }
        """)
    
    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                files.append(file_path)
        
        self.setStyleSheet("""
            QLabel {
                border: 3px dashed #aaa;
                border-radius: 10px;
                background-color: #f5f5f5;
                font-size: 16px;
                color: #666;
            }
            QLabel:hover {
                border-color: #4a90d9;
                background-color: #e8f4fc;
            }
        """)
        
        if files:
            self.files_dropped.emit(files)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ED2K & SHA1 哈希生成器")
        self.setMinimumSize(800, 600)
        self.worker = None
        self.pending_files = []
        self.results = []
        
        self.init_ui()
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title_label = QLabel("ED2K & SHA1 哈希生成器")
        title_label.setFont(QFont("Microsoft YaHei", 18, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        self.drop_label = DropLabel()
        self.drop_label.files_dropped.connect(self.on_files_dropped)
        layout.addWidget(self.drop_label)
        
        btn_layout = QHBoxLayout()
        
        self.select_btn = QPushButton("📂 选择文件")
        self.select_btn.setFont(QFont("Microsoft YaHei", 11))
        self.select_btn.setMinimumHeight(40)
        self.select_btn.clicked.connect(self.select_files)
        btn_layout.addWidget(self.select_btn)
        
        self.start_btn = QPushButton("▶️ 开始处理")
        self.start_btn.setFont(QFont("Microsoft YaHei", 11))
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        self.start_btn.clicked.connect(self.start_processing)
        self.start_btn.setEnabled(False)
        btn_layout.addWidget(self.start_btn)
        
        self.clear_btn = QPushButton("🗑️ 清空")
        self.clear_btn.setFont(QFont("Microsoft YaHei", 11))
        self.clear_btn.setMinimumHeight(40)
        self.clear_btn.clicked.connect(self.clear_all)
        btn_layout.addWidget(self.clear_btn)
        
        layout.addLayout(btn_layout)
        
        file_group = QGroupBox("待处理文件列表")
        file_group.setFont(QFont("Microsoft YaHei", 10))
        file_layout = QVBoxLayout(file_group)
        
        self.file_list = QListWidget()
        self.file_list.setFont(QFont("Microsoft YaHei", 10))
        self.file_list.setMaximumHeight(120)
        file_layout.addWidget(self.file_list)
        
        self.file_count_label = QLabel("共 0 个文件")
        self.file_count_label.setFont(QFont("Microsoft YaHei", 10))
        file_layout.addWidget(self.file_count_label)
        
        layout.addWidget(file_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Microsoft YaHei", 10))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        result_group = QGroupBox("生成结果")
        result_group.setFont(QFont("Microsoft YaHei", 10))
        result_layout = QVBoxLayout(result_group)
        
        self.result_text = QTextEdit()
        self.result_text.setFont(QFont("Consolas", 10))
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("ED2K链接和SHA1哈希将显示在这里...")
        self.result_text.setMinimumHeight(150)
        result_layout.addWidget(self.result_text)
        
        copy_btn_layout = QHBoxLayout()
        
        self.copy_ed2k_btn = QPushButton("📋 复制ED2K链接")
        self.copy_ed2k_btn.setFont(QFont("Microsoft YaHei", 10))
        self.copy_ed2k_btn.clicked.connect(lambda: self.copy_to_clipboard('ed2k'))
        copy_btn_layout.addWidget(self.copy_ed2k_btn)
        
        self.copy_sha1_btn = QPushButton("📋 复制SHA1")
        self.copy_sha1_btn.setFont(QFont("Microsoft YaHei", 10))
        self.copy_sha1_btn.clicked.connect(lambda: self.copy_to_clipboard('sha1'))
        copy_btn_layout.addWidget(self.copy_sha1_btn)
        
        self.copy_all_btn = QPushButton("📋 复制全部")
        self.copy_all_btn.setFont(QFont("Microsoft YaHei", 10))
        self.copy_all_btn.clicked.connect(lambda: self.copy_to_clipboard('all'))
        copy_btn_layout.addWidget(self.copy_all_btn)
        
        result_layout.addLayout(copy_btn_layout)
        layout.addWidget(result_group)
    
    def select_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择文件", "", "所有文件 (*.*)"
        )
        if file_paths:
            self.add_files(file_paths)
    
    def on_files_dropped(self, files):
        self.add_files(files)
    
    def add_files(self, files):
        for file_path in files:
            if file_path not in self.pending_files:
                self.pending_files.append(file_path)
                item = QListWidgetItem(f"📄 {os.path.basename(file_path)}")
                self.file_list.addItem(item)
        
        self.file_count_label.setText(f"共 {len(self.pending_files)} 个文件")
        self.start_btn.setEnabled(len(self.pending_files) > 0)
    
    def start_processing(self):
        if not self.pending_files:
            return
        
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        
        self.results = []
        self.result_text.clear()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.start_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.status_label.setText("正在处理...")
        
        self.worker = HashWorker(self.pending_files.copy())
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_single.connect(self.on_finished_single)
        self.worker.finished_all.connect(self.on_finished_all)
        self.worker.error.connect(self.on_error)
        self.worker.start()
    
    def on_progress(self, file_progress: int, current_file: int, total_files: int):
        overall = int((current_file - 1) / total_files * 100 + file_progress / total_files)
        self.progress_bar.setValue(overall)
        self.status_label.setText(f"正在处理: 第 {current_file}/{total_files} 个文件 ({file_progress}%)")
    
    def on_finished_single(self, file_name: str, file_size: int, ed2k_hash: str, sha1_hash: str):
        ed2k_link = generate_ed2k_link(file_name, file_size, ed2k_hash)
        self.results.append({
            'name': file_name,
            'size': file_size,
            'ed2k': ed2k_link,
            'sha1': sha1_hash
        })
    
    def on_finished_all(self):
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"处理完成! 共 {len(self.results)} 个文件")
        self.start_btn.setEnabled(True)
        self.select_btn.setEnabled(True)
        
        ed2k_links = []
        sha1_hashes = []
        for r in self.results:
            ed2k_links.append(r['ed2k'])
            sha1_hashes.append(f"{r['name']}: {r['sha1']}")
        
        result_text = "=== ED2K 链接 ===\n" + "\n".join(ed2k_links)
        result_text += "\n\n=== SHA1 哈希 ===\n" + "\n".join(sha1_hashes)
        self.result_text.setPlainText(result_text)
    
    def on_error(self, error_msg: str):
        self.result_text.append(f"错误: {error_msg}")
    
    def copy_to_clipboard(self, copy_type: str):
        if not self.results:
            return
        
        text = ""
        if copy_type == 'ed2k':
            text = "\n".join(r['ed2k'] for r in self.results)
        elif copy_type == 'sha1':
            text = "\n".join(f"{r['name']}: {r['sha1']}" for r in self.results)
        else:
            ed2k_links = "\n".join(r['ed2k'] for r in self.results)
            sha1_hashes = "\n".join(f"{r['name']}: {r['sha1']}" for r in self.results)
            text = f"=== ED2K 链接 ===\n{ed2k_links}\n\n=== SHA1 哈希 ===\n{sha1_hashes}"
        
        QApplication.clipboard().setText(text)
        
        btn_map = {
            'ed2k': self.copy_ed2k_btn,
            'sha1': self.copy_sha1_btn,
            'all': self.copy_all_btn
        }
        btn = btn_map[copy_type]
        original_text = btn.text()
        btn.setText("✅ 已复制!")
        QTimer.singleShot(1500, lambda: btn.setText(original_text))
    
    def clear_all(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        
        self.pending_files = []
        self.results = []
        self.file_list.clear()
        self.result_text.clear()
        self.file_count_label.setText("共 0 个文件")
        self.status_label.setText("")
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(False)


from PyQt6.QtCore import QTimer


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
