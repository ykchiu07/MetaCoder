import os
import sys
import tkinter as tk
import threading

# 路徑設定
sys.path.append(os.path.join(os.path.dirname(__file__), 'Generate'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'Dynamic'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'Static'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'System'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'GUI'))

# Backend Imports
from ProjectManager import ProjectManager
from CodeImplementer import CodeImplementer
from TestSpawner import TestSpawner
from ChaosSpawner import ChaosSpawner
from MetricCollector import MetricCollector
from RuntimeAnalyst import RuntimeAnalyst
from ChaosExecuter import ChaosExecuter
from VersionController import VersionController
from StructureAnalyzer import StructureAnalyzer

# Frontend Import
from MainWindow import MainWindow

class MetaCoder:
    def __init__(self, workspace_root: str = "./vibe_workspace", model_name: str = "gemma3:12b"):
        self.workspace_root = os.path.abspath(workspace_root)
        self.model_name = model_name

        # --- Backend Subsystems ---
        self.vc = VersionController(self.workspace_root)
        self.pm = ProjectManager(self.workspace_root)
        self.coder = CodeImplementer()
        self.tester = TestSpawner()
        self.chaos_spawner = ChaosSpawner()
        self.chaos_runner = ChaosExecuter(self.workspace_root)
        self.collector = MetricCollector()
        self.analyst = RuntimeAnalyst()
        self.static_analyzer = StructureAnalyzer(self.workspace_root)

        # State
        self.current_architecture_path = None

        self.model_config = {
            "architect": "gemma3:12b", # 架構生成
            "coder": "gemma3:12b",     # 程式碼實作
            "analyst": "gemma3:12b",   # 邏輯分析
            "vision": "gemma3:4b"      # 視覺分析
        }

    # [新增] 更新模型設定的方法
    def update_model_config(self, role: str, model_name: str):
        if role in self.model_config:
            self.model_config[role] = model_name
            print(f"[Meta] Model for {role} updated to {model_name}")

    def run(self):
        """啟動 GUI 主迴圈"""
        root = tk.Tk()
        # 將自己 (Controller) 傳入 GUI (View)
        app = MainWindow(root, self)
        root.mainloop()

    # --- 業務邏輯 (Business Logic) ---
    # 這些方法供 GUI 元件呼叫

    def init_project(self, req: str):
       # 使用 architect 模型
        model = self.model_config["architect"]
        print(f"[Meta] Initializing project with {model}...")
        res = self.pm.generateHighStructure(req, model)
        self.current_architecture_path = res.structure_file_path
        self.vc.archiveVersion(f"Init: {req[:20]}")
        return res

    def get_project_tree(self):
        if not self.current_architecture_path: return {}
        with open(self.current_architecture_path, 'r') as f:
            return json.load(f)

    def implement_functions(self, spec_path: str, func_names: list):
        # 使用 coder 模型
        results = self.coder.generateFunctionCode(
            spec_path, func_names, self.model_config["coder"], max_workers=2
        )
        # ...
        return results

    # ... (其餘後端邏輯與之前相同，此處省略以節省篇幅) ...
    # 關鍵是確保所有後端操作都在這裡定義，GUI 只是觸發者

if __name__ == "__main__":
    app = MetaCoder()
    app.run()
