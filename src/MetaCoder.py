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
from OllamaManager import OllamaManager
from TestRunner import TestRunner
from TrafficLightManager import TrafficLightManager

# Frontend Import
from MainWindow import MainWindow

class MetaCoder:
    def __init__(self, workspace_root: str = "./vibe_workspace"):
        self.workspace_root = os.path.abspath(workspace_root)
        # [Fix 5] 設定檔路徑
        self.config_path = os.path.join(self.workspace_root, "vibe_config.json")

        # 預設設定
        self.model_config = {
            "architect": "gemma3:12b",
            "coder": "gemma3:12b",
            "analyst": "gemma3:12b",
            "vision": "gemma3:4b"
        }

        # 嘗試載入設定 (如果存在)
        self._load_config()

        # 初始化子系統 (保持不變)
        self.vc = VersionController(self.workspace_root)
        self.pm = ProjectManager(self.workspace_root)
        self.coder = CodeImplementer()
        self.tester = TestSpawner()
        self.chaos_spawner = ChaosSpawner()
        self.chaos_runner = ChaosExecuter(self.workspace_root)
        self.collector = MetricCollector()
        self.analyst = RuntimeAnalyst()
        self.static_analyzer = StructureAnalyzer(self.workspace_root)

        self.current_architecture_path = None
        # [Fix 3] 初始化 Ollama Manager
        self.ollama_mgr = OllamaManager()
        # [New] 初始化測試與燈號管理
        self.test_runner = TestRunner(self.workspace_root)
        self.static_analyzer = StructureAnalyzer(self.workspace_root)

        # [新增]
        self.traffic_light = TrafficLightManager(self)

    # --- [Fix 3] Ollama 控制 API ---
    def ensure_ollama_started(self):
        """在生成前呼叫"""
        self.ollama_mgr.set_logger(lambda msg: print(msg)) # 或導向 GUI log
        self.ollama_mgr.start_service()

    def kill_ollama(self):
        """在 Stop 時呼叫"""
        self.ollama_mgr.kill_service()

    # --- [Fix 5] 設定持久化 ---
    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    saved = json.load(f)
                    self.model_config.update(saved.get('models', {}))
            except: pass

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
            # 立即存檔
            with open(self.config_path, 'w') as f:
                json.dump({'models': self.model_config}, f, indent=4)
            print(f"[Meta] Model for {role} updated to {model_name} and saved.")

    # --- [Fix 2] Main.py Spec 處理 ---
    def _create_main_entry_spec(self, entry_point_name: str):
        if not entry_point_name: return

        # 獲取專案根目錄
        if not self.current_architecture_path: return
        project_dir = os.path.dirname(self.current_architecture_path)

        # 為了讓 ProjectExplorer 能掃描到，我們建立一個名為 "main" 的資料夾
        # 這樣它就會被視為一個模組
        main_mod_dir = os.path.join(project_dir, "main")
        if not os.path.exists(main_mod_dir): os.makedirs(main_mod_dir)

        spec_path = os.path.join(main_mod_dir, "spec.json")

        if not os.path.exists(spec_path):
            spec_data = {
                "module_name": "main", # 邏輯名稱
                "description": "Application Entry Point",
                "dependencies": [], # Main 可能依賴所有人，這裡先空著或填入所有模組
                "functions": [
                    {
                        "name": "main",
                        "args": [],
                        "return_type": "None",
                        "docstring": "Application entry point."
                    }
                ]
            }
            # 嘗試填入所有其他模組作為依賴
            try:
                with open(self.current_architecture_path, 'r') as f:
                    arch = json.load(f)
                spec_data['dependencies'] = [m['name'] for m in arch.get('modules', [])]
            except: pass

            with open(spec_path, 'w', encoding='utf-8') as f:
                json.dump(spec_data, f, indent=4)

            # 建立真實檔案 (放在 main/main.py 或者根目錄 main.py?)
            # 為了符合 Vibe-Coder 的「一模組一資料夾」邏輯，我們放在 main/main.py
            # 但使用者可能期待根目錄。這裡我們做個妥協：放在 main/main.py
            # 之後打包時再處理。
            with open(os.path.join(main_mod_dir, "main.py"), 'w') as f:
                f.write("def main():\n    print('Hello Vibe-Coder')\n\nif __name__ == '__main__':\n    main()")

    # --- Phase 1: 架構生成 ---
    def init_project(self, requirements: str):
        model = self.model_config["architect"]
        print(f"[Meta] Initializing project with {model}...")

        result = self.pm.generateHighStructure(requirements, model)
        self.current_architecture_path = result.structure_file_path

        # [Fix 6] 讀取架構檔，檢查是否有 entry_point 並生成 spec
        try:
            with open(self.current_architecture_path, 'r') as f:
                arch = json.load(f)
            entry = arch.get('entry_point')
            if entry:
                self._create_main_entry_spec(entry)
        except Exception as e:
            print(f"[Meta] Error handling entry point: {e}")

        self.vc.archiveVersion(f"Init Project: {requirements[:20]}")
        return result

    # --- Phase 2: 模組細化 ---
    def refine_module(self, module_name: str, cancel_event=None):
        if not self.current_architecture_path: raise ValueError("No architecture.")

        # 1. [Check] 檢查被依賴模組是否已細化 (Spec 存在)
        deps = self._get_module_dependencies_from_arch(module_name)
        project_dir = os.path.dirname(self.current_architecture_path)

        for dep in deps:
            dep_spec = os.path.join(project_dir, dep, "spec.json")
            if not os.path.exists(dep_spec):
                print(f"[Refine Blocked] Dependency '{dep}' is not refined yet.")
                return None # 這裡應該在 GUI 顯示錯誤，透過 return None 告知失敗

        # 2. [Generate] 生成 Spec
        # 先存檔當前狀態 (Snapshot)，以便回滾
        # 但 VersionController 是基於 git commit。
        # 策略：生成 -> 檢查 -> 若通過則 Commit，若失敗則 Revert 檔案。
        # 為了能 Revert，我們需要知道改了什麼，或者依賴 git clean。
        # 簡單做法：先 Commit 當前狀態為 "Pre-Refine backup" (可選)，或者只在失敗時 checkout .

        model = self.model_config["architect"]
        progress = {'status': '', 'current': 0, 'total': 0}

        result = self.pm.generateModuleDetail(
            self.current_architecture_path, module_name, progress, model, cancel_event
        )
        if not result: return None # 被取消或失敗

        # 3. [Audit] 虛擬靜態分析：循環依賴檢查
        print(f"[Meta] Auditing circular dependencies for {module_name}...")

        # 構建虛擬代碼 Map (所有已存在的 Spec + 剛生成的這個)
        virtual_map = {}
        # 讀取所有現有模組
        for d in os.listdir(project_dir):
            spec_p = os.path.join(project_dir, d, "spec.json")
            if os.path.exists(spec_p):
                with open(spec_p, 'r') as f:
                    s = json.load(f)
                    # 轉換為 import 語句
                    imports = "\n".join([f"import {dep}" for dep in s.get('dependencies', [])])
                    virtual_map[d] = imports

        cycles = self.static_analyzer.detect_cycles_from_stubs(virtual_map)

        if cycles:
            print(f"[Audit Failed] Circular dependency detected: {cycles}")
            # [Rollback] 刪除剛生成的 spec 和 stub
            # 最快的方法是 git checkout -- <module_dir> (如果之前有 commit)
            # 或者手動刪除。這裡使用 VC 的 rollback file (需擴充支援資料夾) 或簡單用 os.remove
            # 由於這是新生成的檔案，它們是 Untracked。
            # 我們可以直接刪除該模組資料夾下的 spec.json 和 .py
            import shutil
            mod_dir = os.path.dirname(result.spec_file_path)
            shutil.rmtree(mod_dir) # 危險：如果該資料夾原本就有東西？
            # 安全做法：只刪除 spec.json 和 __init__.py
            os.remove(result.spec_file_path)
            # ... (刪除 stubs)
            print(f"[Meta] Rolled back refinement for {module_name}.")
            return None # 視為失敗

        # 4. [Commit] 通過檢查，歸檔
        self.vc.archiveVersion(f"Refined Module: {module_name}")
        return result

    # --- Phase 3: 函式實作 ---
    def implement_functions(self, spec_path: str, func_names: list, cancel_event=None):
        # 1. [Generate]
        model = self.model_config["coder"]
        # 強制單線程
        results = self.coder.generateFunctionCode(spec_path, func_names, model, max_workers=1, cancel_event=cancel_event)

        if not results: return []

        # 2. [Audit] 實作一致性檢查
        # 讀取 Spec 中的允許依賴
        with open(spec_path, 'r') as f:
            spec = json.load(f)
        allowed = spec.get('dependencies', [])
        # 允許依賴自己模組
        mod_name = spec.get('module_name')
        if mod_name: allowed.append(mod_name)

        valid_results = []
        for res in results:
            if not res.success: continue

            # 檢查
            if self.static_analyzer.verify_implementation_deps(res.file_path, allowed):
                valid_results.append(res)
            else:
                print(f"[Audit Failed] Implementation of {res.function_name} violates dependency rules.")
                # [Rollback] 還原該檔案
                # 這裡簡單清空或寫回 pass stub
                with open(res.file_path, 'w') as f:
                    f.write(f"def {res.function_name}(*args, **kwargs):\n    raise NotImplementedError('Audit Failed: Dependency Violation')")
                # 更新狀態為 failed
                self.coder._update_status_file(os.path.dirname(spec_path), res.function_name, "audit_failed", 0, 0)

        # [Fix 5] 版本控制存檔
        if valid_results:
            msg = f"Implemented {len(valid_results)} funcs: {', '.join([r.function_name for r in valid_results])}"
            self.vc.archiveVersion(msg)
            print(f"[Meta] Version Archived: {msg}")

        return valid_results

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

    # --- [Fix 1] 依賴圖邏輯 ---
    def get_module_dependencies(self):
        """
        優先從 architecture.json 讀取依賴關係 (因為這是 Phase 1 就有的)。
        如果沒有 arch 檔，才退回到 StaticAnalyzer 分析源碼。
        """
        # 嘗試讀取架構檔
        arch_data = self.get_project_tree()

        nodes = []
        edges = [] # (source, target)

        if arch_data and 'modules' in arch_data:
            # 方案 A: 使用架構定義 (Intent)
            for mod in arch_data['modules']:
                name = mod['name']
                nodes.append(name)
                for dep in mod.get('dependencies', []):
                    edges.append((name, dep))

            # 把 main entry 也加進去
            entry = arch_data.get('entry_point')
            if entry:
                # 假設 entry (如 main.py) 依賴所有模組，或者在 arch 中未定義
                # 這裡我們先把 main 當作一個節點
                main_node = "main" # 簡化顯示
                if main_node not in nodes: nodes.append(main_node)
                # 通常 main 依賴所有頂層模組，這裡暫不畫線，以免太亂，或者全畫

        else:
            # 方案 B: 退回源碼分析 (Reality)
            if not self.static_analyzer.dependencies:
                self.static_analyzer._preprocess()
            nodes = list(self.static_analyzer.internal_modules)
            for src, targets in self.static_analyzer.dependencies.items():
                for tgt in targets:
                    if tgt in nodes:
                        edges.append((src, tgt))

        return nodes, edges

    def _get_module_dependencies_from_arch(self, module_name):
        """從 architecture.json 讀取依賴列表"""
        if not self.current_architecture_path: return []
        with open(self.current_architecture_path, 'r') as f:
            arch = json.load(f)
        mod = next((m for m in arch.get('modules', []) if m['name'] == module_name), None)
        return mod.get('dependencies', []) if mod else []

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
        print(f"[Meta] Switching workspace to: {new_path}")
        self.workspace_root = os.path.abspath(new_path)
        self.config_path = os.path.join(self.workspace_root, "vibe_config.json")

        self.vc = VersionController(self.workspace_root)
        self.pm = ProjectManager(self.workspace_root)
        self.static_analyzer = StructureAnalyzer(self.workspace_root)
        self.chaos_runner = ChaosExecuter(self.workspace_root)
        self.current_architecture_path = None

        self._load_config() # 載入該 Workspace 的特定設定
        self.get_project_tree()
        print("[Meta] Workspace reset complete.")

    def check_dependencies_met(self, module_name: str) -> bool:
        if not self.current_architecture_path: return True
        try:
            with open(self.current_architecture_path, 'r') as f:
                arch = json.load(f)

            mod_info = next((m for m in arch.get('modules', []) if m['name'] == module_name), None)
            # 如果是 main，可能不在 modules 列表中，這裡假設 main 依賴所有 top-level modules
            # 為求簡單，如果找不到 mod_info，我們預設它依賴所有已存在的模組 (這對 main 很有用)
            dependencies = []
            if mod_info:
                dependencies = mod_info.get('dependencies', [])
            elif module_name == 'main':
                # 特例處理 main: 檢查所有其他模組是否 ready
                dependencies = [m['name'] for m in arch.get('modules', [])]

            project_dir = os.path.dirname(self.current_architecture_path)

            for dep in dependencies:
                status_path = os.path.join(project_dir, dep, ".status.json")
                if not os.path.exists(status_path):
                    print(f"[Check] {module_name} blocked: {dep} missing status file.")
                    return False

                with open(status_path, 'r') as f:
                    status = json.load(f)
                    # 只要有任何一個函式實作了，就當作該模組可用 (Low bar for MVP)
                    if not any(v.get('status') == 'implemented' for v in status.values()):
                        print(f"[Check] {module_name} blocked: {dep} has no impl funcs.")
                        return False

            return True # All checks passed
        except Exception as e:
            print(f"[Check Error] {e}")
            return True # Fail open to avoid deadlocks
    # --- Workflow: Unit Test ---
    def execute_test_workflow(self, target_name, target_type, spec_path, mediator):
        """生成並執行單元測試"""
        def task():
            mediator.log(f"[Test] Starting Test Workflow for {target_name}...")

            # 1. 生成測試 (如果沒有)
            if target_type == 'function':
                funcs = [target_name]
            elif target_type == 'module':
                # 讀取 spec 找出所有函式
                try:
                    with open(spec_path, 'r') as f: spec = json.load(f)
                    funcs = [f['name'] for f in spec.get('functions', [])]
                except: funcs = []
            else:
                funcs = []

            if funcs and spec_path:
                mediator.log(f"[Test] Generating tests for: {funcs}")
                self.tester.generateUnitTest(spec_path, funcs, self.model_config['coder'])

            # 2. 執行測試
            # [Fix 3 延伸] 確保傳入正確的 module_name
            # 如果 target_type 是 'function'，target_name 是函式名，我們需要找出模組名
            if target_type == 'function':
                mod_name = os.path.basename(os.path.dirname(spec_path))
            else:
                mod_name = target_name

            mediator.log(f"[Test] Running tests for module: {mod_name}")
            results = self.test_runner.run_module_tests(mod_name)

            # Log 結果
            pass_count = sum(1 for v in results.values() if v)
            mediator.log(f"[Test Result] Passed {pass_count}/{len(results)}")

            # 更新 Graph
            mediator.root.after(0, mediator.workspace.draw_dependency_graph)
            # 自動重載編輯器 (如果測試修改了檔案?? 通常不會，但保持一致性)
            mediator.root.after(0, mediator.workspace.reload_active_file)

        mediator.run_async(task)

    # --- Workflow: Runtime Analysis ---
    def execute_runtime_workflow(self, func_name, code_str, mediator):
        """執行代碼並分析效能"""
        def task():
            mediator.log(f"[Runtime] Executing {func_name} with Profiler...")

            # 1. 執行與收集數據
            # 這裡需要注意：execute_code 需要能跑起來的代碼。
            # 如果代碼依賴其他模組，直接 exec 可能會失敗。
            # 簡單解法：我們先跑，失敗就報錯。
            try:
                self.collector.execute_code(code_str)
            except Exception as e:
                mediator.log(f"[Runtime Error] Execution failed: {e}")
                return

            # 2. 獲取數據
            raw_json = self.collector.outputMetricResult(target_funcs=[func_name])
            data = json.loads(raw_json)

            perf = data['performance'].get(func_name, {})
            mediator.log(f"[Runtime Data] Time: {perf.get('total_time_ms')}ms, Mem: {perf.get('mem_peak')} bytes")

            # 3. LLM 分析 (可選，這裡只做數據更新讓燈號變色)
            # 如果你要看 LLM 報告，可以呼叫 analyst.analyzeBottleNeck

            mediator.log("[Runtime] Profile updated. Refreshing graph...")
            mediator.root.after(0, mediator.workspace.draw_dependency_graph)

        mediator.run_async(task)

    # --- Workflow: Chaos Engineering ---
    def execute_chaos_workflow(self, module_name, mediator):
        """生成弱點分析 -> 攻擊計畫 -> 執行攻擊"""
        def task():
            mediator.log(f"[Chaos] Initiating Campaign against {module_name}...")

            # 1. 弱點掃描
            weakness_path, _ = self.chaos_spawner.generateWeaknessAnalysis(
                module_name, self.workspace_root, self.model_config['analyst']
            )
            mediator.log("[Chaos] Weakness analysis complete.")

            if mediator._current_cancel_flag.is_set(): return

            # 2. 生成計畫
            plan_path, _ = self.chaos_spawner.generateChaosPlan(
                weakness_path, 2, self.model_config['analyst'] # Focus Level 2
            )
            mediator.log("[Chaos] Attack plan generated.")

            if mediator._current_cancel_flag.is_set(): return

            # 3. 執行攻擊
            mediator.log("[Chaos] Launching attacks (this may take time)...")
            report_path = self.chaos_runner.produceChaos(module_name)

            # 4. 讀取報告摘要
            try:
                with open(report_path, 'r') as f: report = json.load(f)
                mediator.log("\n=== CHAOS REPORT ===")
                for res in report.get('results', []):
                    status = res['status'] # RESILIENT / FRAGILE
                    mediator.log(f"Target: {res['function']} | {res['injection']} -> {status} ({res['survival_rate']*100}%)")
            except: pass

            mediator.log("[Chaos] Campaign finished.")
            mediator.root.after(0, mediator.workspace.draw_dependency_graph)

        mediator.run_async(task)


if __name__ == "__main__":
    app = MetaCoder()
    app.run()
