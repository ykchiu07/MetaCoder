import os
import json
import statistics
from typing import Dict, Any

class TrafficLightManager:
    """
    負責將各種指標轉換為視覺燈號 (紅/黃/綠)
    核心邏輯：Data -> Normalization -> Score -> Color
    """
    GREEN = "#50fa7b"   # 通過/優良
    YELLOW = "#ffb86c"  # 警告/中等
    RED = "#ff5555"     # 失敗/嚴重
    GRAY = "#6272a4"    # 無數據

    def __init__(self, meta_coder):
        self.meta = meta_coder

    def get_color(self, view_mode: str, data_mode: str, node_name: str, parent_mod: str = None) -> str:
        """
        統一入口點。
        Args:
            view_mode: 'module' | 'function'
            data_mode: 'creation', 'general_test', 'static_eval', 'runtime_analysis', 'chaos_test'
            node_name: 模組名 或 函式名
            parent_mod: 如果是 function view，這裡需要傳入所屬模組名
        """
        # 0. Creation Mode (預設藍色)
        if data_mode == 'creation':
            return "#4a88c7"

        # 1. Static Evaluation (靜態評估)
        if data_mode == 'static_eval':
            if view_mode == 'module':
                return self._eval_static_module(node_name)
            elif view_mode == 'function':
                return self._eval_static_function(node_name, parent_mod)

        # 2. Runtime Analysis (執行期分析)
        elif data_mode == 'runtime_analysis':
            # Runtime 在 Module view 是平均值，Function view 是絕對值
            return self._eval_runtime(view_mode, node_name, parent_mod)

        # 3. Chaos Engineering (混沌工程)
        elif data_mode == 'chaos_test':
            return self._eval_chaos(view_mode, node_name, parent_mod)

        # 4. General Test (單元測試)
        elif data_mode == 'general_test':
            # 由於時間緊迫，測試狀態暫時依賴 .status.json 或預設灰色
            # 未來應連接 TestRunner 的即時結果
            return self.GRAY

        return self.GRAY

    # --- Static Eval Logic ---

    def _eval_static_module(self, mod_name: str) -> str:
        """
        [Module View] Static Eval
        依賴 StructureAnalyzer 計算：
        1. 耦合度 (Coupling Score)
        2. 內聚性 (Cohesion - LCOM4 & Density)
        """
        analyzer = self.meta.static_analyzer

        # A. 耦合度 (0-100, 越高越好)
        coupling_score = analyzer.calculateCoupling(mod_name)

        # B. 內聚性 (需聚合該模組下所有類別的 LCOM4)
        cohesion_data = analyzer.calculateCohesion(mod_name)
        # cohesion_data = {'ClassName': {'lcom4': int, 'density': float}}

        if not cohesion_data:
            # 如果沒有類別，只看耦合度
            return self._score_to_color(coupling_score)

        # 計算平均 LCOM4 (越低越好，1是最好)
        lcom_values = [d['lcom4'] for d in cohesion_data.values()]
        avg_lcom = statistics.mean(lcom_values)

        # 綜合評分邏輯
        # 若 LCOM > 2，扣分嚴重
        lcom_penalty = 0
        if avg_lcom > 1: lcom_penalty = 20
        if avg_lcom > 2: lcom_penalty = 50

        final_score = coupling_score - lcom_penalty
        return self._score_to_color(final_score)

    def _eval_static_function(self, func_name: str, mod_name: str) -> str:
        """
        [Function View] Static Eval
        依賴 CodeAnalyzer 計算：
        1. 維護性指標 (MI)
        2. 圈複雜度 (CC)
        """
        try:
            # 讀取原始碼
            # 這裡做一個簡單的 I/O 優化：如果 CodeAnalyzer 已經快取了該檔案則直接用
            # 但目前架構 CodeAnalyzer 是針對 string，所以我們需讀檔
            mod_dir = os.path.join(self.meta.workspace_root, mod_name)
            filename = "__init_logic__.py" if func_name == "__init__" else f"{func_name}.py"
            path = os.path.join(mod_dir, filename)

            if not os.path.exists(path): return self.GRAY

            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()

            # 使用 CodeAnalyzer
            from CodeAnalyzer import CodeAnalyzer
            analyzer = CodeAnalyzer(code)

            # 1. MI Score (0-100)
            mi = analyzer.calculateMaintainability()

            # 2. CC (Cyclomatic Complexity) - 硬性門檻
            # cc_visit 回傳 dict {'func_name': cc}
            cc_data = analyzer.calculateComplexity()
            # 由於我們只傳入了單一函式的程式碼，cc_data 應該只有一項，或 func_name 匹配
            # 簡單取最大值
            max_cc = max(cc_data.values()) if cc_data else 0

            # 評分規則
            if max_cc > 20: return self.RED     # 複雜度過高，直接紅燈
            if max_cc > 10: return self.YELLOW  # 複雜度中等

            return self._score_to_color(mi)     # 否則依據 MI 決定

        except Exception as e:
            # print(f"Static Func Eval Error: {e}")
            return self.GRAY

    # --- Runtime Logic ---

    def _eval_runtime(self, view_mode: str, node_name: str, parent_mod: str) -> str:
        """
        [Runtime]
        依賴 MetricCollector 提供的數據
        """
        # 獲取 benchmark 數據
        bench = self.meta.collector.getBenchmarkData()

        if view_mode == 'function':
            data = bench.get(node_name)
            if not data: return self.GRAY

            avg_time = data.get('avg_ms', 0)
            calls = data.get('calls', 0)

            # 絕對指標評分 (針對一般 desktop app)
            # 紅色：明顯卡頓 (>100ms) 或極高頻呼叫累積耗時長
            if avg_time > 100: return self.RED
            if avg_time > 30: return self.YELLOW
            return self.GREEN

        elif view_mode == 'module':
            # 聚合該模組下所有函式的數據
            # 需要先知道該模組有哪些函式 (從 Spec 讀取)
            if not node_name: return self.GRAY
            spec_path = os.path.join(self.meta.workspace_root, node_name, "spec.json")
            if not os.path.exists(spec_path): return self.GRAY

            total_avg_time = 0
            func_count = 0

            try:
                with open(spec_path, 'r') as f:
                    spec = json.load(f)
                for func in spec.get('functions', []):
                    fname = func['name']
                    if fname in bench:
                        total_avg_time += bench[fname].get('avg_ms', 0)
                        func_count += 1
            except: pass

            if func_count == 0: return self.GRAY

            module_avg = total_avg_time / func_count
            if module_avg > 50: return self.RED
            if module_avg > 15: return self.YELLOW
            return self.GREEN

    # --- Chaos Logic ---

    def _eval_chaos(self, view_mode: str, node_name: str, parent_mod: str) -> str:
        """
        [Chaos]
        讀取 chaos_report.json 中的 survival_rate
        """
        target_mod = node_name if view_mode == 'module' else parent_mod
        report_path = os.path.join(self.meta.workspace_root, target_mod, "chaos_report.json")

        if not os.path.exists(report_path): return self.GRAY

        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)

            results = report.get('results', [])
            if not results: return self.GRAY

            if view_mode == 'function':
                # 尋找特定函式
                for res in results:
                    if res['function'] == node_name:
                        return self._rate_to_color(res['survival_rate'])
                return self.GRAY

            elif view_mode == 'module':
                # 計算平均存活率
                avg_rate = statistics.mean([r['survival_rate'] for r in results])
                return self._rate_to_color(avg_rate)

        except: pass
        return self.GRAY

    # --- Helpers ---

    def _score_to_color(self, score: float) -> str:
        """通用分數轉燈號 (0-100)"""
        if score >= 80: return self.GREEN
        if score >= 60: return self.YELLOW
        return self.RED

    def _rate_to_color(self, rate: float) -> str:
        """通用比率轉燈號 (0.0-1.0)"""
        if rate >= 0.8: return self.GREEN
        if rate >= 0.5: return self.YELLOW
        return self.RED
