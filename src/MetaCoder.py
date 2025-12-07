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

        # [修正] 傳入 max_workers=3
        results = self.coder.generateFunctionCode(
            spec_path,
            func_names,
            model,
            max_workers=3, # 您可以根據您的 CPU 核心數調整此值
            cancel_event=cancel_event
        )

        if results: # 只有在有結果時才存檔
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
        """
        [修正] 更強健的 architecture.json 搜尋邏輯。
        """
        # 1. 如果已經有快取路徑且檔案存在，直接用
        if self.current_architecture_path and os.path.exists(self.current_architecture_path):
            try:
                with open(self.current_architecture_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass # 讀取失敗則重搜

        # 2. 搜尋邏輯：優先找根目錄，其次找第一層子目錄
        candidates = []
        # Check root
        p = os.path.join(self.workspace_root, "architecture.json")
        if os.path.exists(p): candidates.append(p)

        # Check subdirs (depth=1)
        if not candidates:
            for d in os.listdir(self.workspace_root):
                full_d = os.path.join(self.workspace_root, d)
                if os.path.isdir(full_d):
                    p = os.path.join(full_d, "architecture.json")
                    if os.path.exists(p): candidates.append(p)

        if candidates:
            self.current_architecture_path = candidates[0] # 取第一個找到的
            try:
                with open(self.current_architecture_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Meta] Error reading arch json: {e}")
                return {}

        return {}

    def get_module_dependencies(self):
        """
        獲取模組依賴關係圖數據供 GUI 繪製。
        Returns:
            nodes: List[str] 模組名稱列表
            edges: List[Tuple[str, str]] 依賴關係 (source, target)
        """
        # 確保有最新的分析
        if not self.static_analyzer.dependencies:
             # 如果尚未初始化或數據為空，嘗試重新掃描一次 (假設已有代碼)
             self.static_analyzer._preprocess()

        # 取得所有內部模組名稱 (Nodes)
        nodes = list(self.static_analyzer.internal_modules)

        # 取得依賴關係 (Edges)
        edges = []
        for src, targets in self.static_analyzer.dependencies.items():
            for tgt in targets:
                if tgt in nodes: # 只顯示內部模組間的依賴
                    edges.append((src, tgt))

        return nodes, edges

    def get_function_distribution(self):
        """
        [修正] 聚合模組名稱，解決 Legend 過於破碎的問題。
        將 'auth.login', 'auth.utils' 統一聚合為 'auth'。
        """
        if not self.static_analyzer.graphs:
            self.static_analyzer._preprocess()

        distribution = {} # { 'module_folder_name': [func_names...] }

        for mod_key, graph in self.static_analyzer.graphs.items():
            # mod_key 可能是 "auth.login" 或 "main"
            # 我們只取最頂層的模組名稱 (即資料夾名稱)
            # 如果是 'auth.login' -> top_mod = 'auth'
            # 如果是 'main' -> top_mod = 'main'
            top_mod = mod_key.split('.')[0]

            # 排除一些非業務邏輯的根節點 (視情況而定，這裡先保留)

            funcs = []
            for _, data in graph.graph.nodes(data=True):
                if data.get('type') == 'function':
                    funcs.append(data.get('name'))

            if funcs:
                if top_mod not in distribution:
                    distribution[top_mod] = []
                # 合併並去重
                distribution[top_mod].extend(funcs)
                # distribution[top_mod] = list(set(distribution[top_mod])) # 若有需要去重

        return distribution

    def set_workspace(self, new_path: str):
        """
        [關鍵修正] 切換工作區並重置所有後端狀態。
        防止舊專案的資料殘留。
        """
        print(f"[Meta] Switching workspace to: {new_path}")
        self.workspace_root = os.path.abspath(new_path)

        # 1. 強制重新初始化所有依賴路徑的子系統
        self.vc = VersionController(self.workspace_root)
        self.pm = ProjectManager(self.workspace_root)
        self.static_analyzer = StructureAnalyzer(self.workspace_root) # 清空舊的依賴圖
        self.chaos_runner = ChaosExecuter(self.workspace_root)

        # 2. 清空快取狀態
        self.current_architecture_path = None

        # 3. 嘗試自動載入新專案的架構檔 (如果存在)
        # 這裡會更新 current_architecture_path，讓 ProjectExplorer 的監控迴圈能抓到
        self.get_project_tree()

        print("[Meta] Workspace reset complete.")

    def check_dependencies_met(self, module_name: str) -> bool:
        """
        [新增] 檢查某模組的依賴是否都已經實作完畢。
        規則：依賴模組必須至少有一個函式被標記為 implemented。
        """
        if not self.current_architecture_path: return True

        try:
            with open(self.current_architecture_path, 'r') as f:
                arch = json.load(f)

            mod_info = next((m for m in arch.get('modules', []) if m['name'] == module_name), None)
            if not mod_info: return True

            project_dir = os.path.dirname(self.current_architecture_path)

            for dep in mod_info.get('dependencies', []):
                # 檢查依賴模組的 status.json
                status_path = os.path.join(project_dir, dep, ".status.json")
                if not os.path.exists(status_path):
                    print(f"[Dependency Check] {module_name} blocked: Dependency '{dep}' has no status file.")
                    return False

                # 檢查是否有任何 implemented 的函式
                with open(status_path, 'r') as f:
                    status = json.load(f)
                    # 簡單檢查：只要有任何 key 的 status 是 implemented 就算通過
                    # 更嚴謹的檢查需要依賴細粒度的 function call graph，這裡先做模組級檢查
                    if not any(v.get('status') == 'implemented' for v in status.values()):
                        print(f"[Dependency Check] {module_name} blocked: Dependency '{dep}' has no implemented functions.")
                        return False

            return True

        except Exception as e:
            print(f"[Dependency Check] Error: {e}")
            return True # 出錯時預設不擋，以免死鎖

if __name__ == "__main__":
    app = MetaCoder()
    app.run()
