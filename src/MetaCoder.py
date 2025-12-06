import os
import json
import sys
import tkinter as tk

# 設定模組搜尋路徑，確保能 import 子資料夾中的模組
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
    def __init__(self, workspace_root: str = "./vibe_workspace"):
        self.workspace_root = os.path.abspath(workspace_root)

        # [Config] 模型角色設定 (預設值)
        self.model_config = {
            "architect": "gemma3:12b",  # 負責架構生成、Spec 細化
            "coder": "gemma3:12b",      # 負責寫程式碼 (需較強邏輯)
            "analyst": "gemma3:12b",    # 負責瓶頸分析、弱點掃描
            "vision": "gemma3:4b"       # 負責 GUI 截圖分析
        }

        # [Backend] 初始化所有子系統
        self.vc = VersionController(self.workspace_root)
        self.pm = ProjectManager(self.workspace_root)
        self.coder = CodeImplementer()
        self.tester = TestSpawner()
        self.chaos_spawner = ChaosSpawner()
        self.chaos_runner = ChaosExecuter(self.workspace_root)
        self.collector = MetricCollector()
        self.analyst = RuntimeAnalyst()
        self.static_analyzer = StructureAnalyzer(self.workspace_root)

        # [State] 當前狀態快取
        self.current_architecture_path = None

    def run(self):
        """啟動 GUI 主迴圈"""
        root = tk.Tk()
        # 將自己 (Controller) 傳入 GUI (View)
        app = MainWindow(root, self)
        root.mainloop()

    # --- 設定管理 ---
    def update_model_config(self, role: str, model_name: str):
        if role in self.model_config:
            self.model_config[role] = model_name
            print(f"[Meta] Model for {role} updated to {model_name}")

    # --- Phase 1: 架構生成 ---
    def init_project(self, requirements: str):
        """生成專案藍圖"""
        model = self.model_config["architect"]
        print(f"[Meta] Initializing project with {model}...")

        result = self.pm.generateHighStructure(requirements, model)

        self.current_architecture_path = result.structure_file_path
        self.vc.archiveVersion(f"Init Project: {requirements[:20]}")
        return result

    # --- Phase 2: 模組細化 ---
    def refine_module(self, module_name: str, cancel_event=None):
        """生成模組 Spec 與 Stubs"""
        if not self.current_architecture_path:
            raise ValueError("No architecture loaded.")

        model = self.model_config["architect"]
        # 簡單的進度字典
        progress = {'status': '', 'current': 0, 'total': 0}

        result = self.pm.generateModuleDetail(
            self.current_architecture_path,
            module_name,
            progress,
            model,
            cancel_event=cancel_event # 傳遞取消旗標
        )

        if result: # 如果沒被取消
            self.vc.archiveVersion(f"Refined Module: {module_name}")
        return result

    # --- Phase 3: 函式實作 ---
    def implement_functions(self, spec_path: str, func_names: list, cancel_event=None):
        """實作指定函式"""
        model = self.model_config["coder"]

        results = self.coder.generateFunctionCode(
            spec_path,
            func_names,
            model,
            max_workers=2,
            cancel_event=cancel_event # 傳遞取消旗標
        )

        self.vc.archiveVersion(f"Implemented {len(func_names)} funcs in {os.path.basename(os.path.dirname(spec_path))}")
        return results

    # --- 測試生成 ---
    def generate_tests(self, spec_path: str, func_names: list):
        """生成單元測試"""
        model = self.model_config["coder"] # 寫測試也算 Coding
        return self.tester.generateUnitTest(spec_path, func_names, model)

    # --- 動態分析與除錯 ---
    def run_dynamic_analysis(self, code_str: str, target_func: str):
        """執行代碼 -> 收集數據 -> LLM 分析"""
        print("[Meta] Starting Dynamic Analysis...")

        # 1. 執行並收集 (LLM-free)
        self.collector.execute_code(code_str)
        raw_json = self.collector.outputMetricResult(target_funcs=[target_func])
        data = json.loads(raw_json)

        # 2. 邏輯瓶頸分析
        model_logic = self.model_config["analyst"]
        logic_report, l_entropy = self.analyst.analyzeBottleNeck(
            target_func,
            data['performance'],
            data['io_activity'],
            data['code_coverage'],
            data['call_graph'],
            logic_model=model_logic
        )

        # 3. 視覺分析 (如果有截圖)
        vision_report = "No GUI detected or captured."
        v_entropy = 0.0

        if data.get('gui_screenshots'):
            model_vision = self.model_config["vision"]
            # 取第一張截圖進行分析
            snapshot_path = data['gui_screenshots'][0]
            vision_report, v_entropy = self.analyst.analyzeSnapshot(
                snapshot_path,
                f"Function context: {target_func}",
                "Auto-analysis: Check for visual anomalies.",
                vision_model=model_vision
            )

        return {
            "metrics": data,
            "logic_report": logic_report,
            "vision_report": vision_report,
            "entropies": (l_entropy, v_entropy)
        }

    # --- 混沌工程 ---
    def run_chaos_campaign(self, module_name: str):
        """弱點分析 -> 生成計畫 -> 執行攻擊"""
        model = self.model_config["analyst"]

        # 1. 分析
        weakness_path, _ = self.chaos_spawner.generateWeaknessAnalysis(
            module_name, self.workspace_root, model
        )
        # 2. 計畫
        plan_path, _ = self.chaos_spawner.generateChaosPlan(
            weakness_path, 2, model # Focus Level 2 (Medium+)
        )
        # 3. 執行
        report_path = self.chaos_runner.produceChaos(module_name)
        return report_path

    # --- 系統操作 ---
    def get_project_tree(self):
        """輔助函式：回傳專案結構供 GUI 顯示"""
        # 如果還沒載入，嘗試自動尋找最新的 architecture.json
        if not self.current_architecture_path:
            # 簡單遍歷 workspace 尋找可能的專案檔
            for root, dirs, files in os.walk(self.workspace_root):
                if "architecture.json" in files:
                    self.current_architecture_path = os.path.join(root, "architecture.json")
                    break

        if not self.current_architecture_path or not os.path.exists(self.current_architecture_path):
            return {}

        with open(self.current_architecture_path, 'r', encoding='utf-8') as f:
            return json.load(f)

if __name__ == "__main__":
    app = MetaCoder()
    app.run()
