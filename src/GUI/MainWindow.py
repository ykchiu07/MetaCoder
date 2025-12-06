import tkinter as tk
from tkinter import ttk
import threading
from ProjectExplorer import ProjectExplorer
from WorkSpace import WorkSpace
from IntelligencePanel import IntelligencePanel
from ControlPanel import ControlPanel

class MainWindow:
    def __init__(self, root, meta_coder):
        self.root = root
        self.meta = meta_coder # 持有 Backend 引用

        self.root.title("Vibe-Coder IDE (Modular Architecture)")
        self.root.geometry("1400x900")

        style = ttk.Style()
        style.theme_use('clam')

        self._init_layout()

    def _init_layout(self):
        # 主分割
        self.main_pane = tk.PanedWindow(self.root, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        # 上半部分割
        self.top_pane = tk.PanedWindow(self.main_pane, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.main_pane.add(self.top_pane, height=700)

        # --- 載入子元件 ---
        # 1. 左側：導航 (傳入 self 作為 mediator)
        self.nav = ProjectExplorer(self.top_pane, self)
        self.top_pane.add(self.nav.frame, width=250)

        # 2. 中間：工作區
        self.workspace = WorkSpace(self.top_pane, self)
        self.top_pane.add(self.workspace.frame, width=800)

        # 3. 右側：智囊
        self.intelligence = IntelligencePanel(self.top_pane, self)
        self.top_pane.add(self.intelligence.frame, width=350)

        # 4. 底部：控制
        self.controls = ControlPanel(self.main_pane, self)
        self.main_pane.add(self.controls.frame)

    # --- 公用服務 (Service Providers for Sub-components) ---

    def log(self, msg):
        """將訊息轉發給 IntelligencePanel"""
        self.intelligence.log(msg)

    def set_status(self, msg):
        """將狀態轉發給 ControlPanel"""
        self.controls.set_status(msg)

    def run_async(self, task_func, success_msg="Done"):
        """通用的非同步執行器"""
        def wrapper():
            try:
                task_func()
                self.set_status(success_msg)
            except Exception as e:
                self.log(f"[Error] {str(e)}")
                self.set_status("Error Occurred")

        self.set_status("Processing...")
        threading.Thread(target=wrapper, daemon=True).start()
