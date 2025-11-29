import os
import math
import networkx as nx
from collections import defaultdict
import ASTGraph, PythonSourceParser

class StructureAnalyzer:
    def __init__(self, work_dir: str):
        self.work_dir = work_dir
        # 識別專案內部的模組清單 (用於區分內部依賴與第三方函式庫)
        self.internal_modules = self._get_internal_modules(work_dir)
        # 儲存每個模組的 ASTGraph 快取: { module_name: ASTGraph }
        self.graphs = {}
        # 儲存模組間依賴關係 (用於 Instability): { module_name: set(imported_modules) }
        self.dependencies = defaultdict(set)

        # 初始化時自動執行預處理
        self._preprocess()

    def _get_internal_modules(self, work_dir):
        """掃描目錄建立內部模組白名單"""
        mods = set()
        for root, _, files in os.walk(work_dir):
            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    # 將路徑轉換為 Python 模組表示法 (e.g., utils.helper)
                    rel_path = os.path.relpath(os.path.join(root, file), work_dir)
                    mod_name = rel_path.replace(os.sep, ".")[:-3]
                    mods.add(mod_name)
                    # 同時加入頂層包名
                    if "." in mod_name:
                        mods.add(mod_name.split('.')[0])
        return mods

    def _preprocess(self):
        """
        一次性解析所有檔案：
        1. 建立 ASTGraph 快取
        2. 建立全域模組依賴圖 (Global Dependency Graph)
        """
        for root, _, files in os.walk(self.work_dir):
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    # 取得模組名稱
                    rel_path = os.path.relpath(path, self.work_dir)
                    mod_name = rel_path.replace(os.sep, ".")[:-3]
                    if file == "__init__.py": # 處理 package
                        mod_name = rel_path.replace(os.sep, ".")[:-12]

                    # 解析程式碼
                    with open(path, 'r', encoding='utf-8') as f:
                        code = f.read()

                    graph = ASTGraph.ASTGraph()
                    analyzer = PythonSourceParser.PythonSourceParser(graph)
                    analyzer.analyze_code(code)

                    self.graphs[mod_name] = graph

                    # 提取依賴關係 (僅針對內部模組)
                    for _, data in graph.graph.nodes(data=True):
                        if data.get('type') == 'import':
                            # 這裡簡化處理 import 字串解析
                            imp_str = data.get('label', '')
                            # 簡單啟發式解析：分割字串並比對白名單
                            for token in imp_str.replace(',', ' ').split():
                                clean_token = token.split('.')[0]
                                if clean_token in self.internal_modules and clean_token != mod_name:
                                    self.dependencies[mod_name].add(clean_token)

    # --- 1. 耦合度 (Coupling) [跨模組] ---
    def calculateCoupling(self, module_name: str) -> float:
        """
        計算指數遞減評分。
        公式: Score = 100 * e^(-0.2 * Ce)
        Ce (Efferent Coupling): 該模組依賴了多少個內部模組。
        """
        if module_name not in self.dependencies:
            return 100.0

        ce = len(self.dependencies[module_name])
        # 使用指數遞減函數，讓高耦合的懲罰加劇
        return round(100.0 * math.exp(-0.2 * ce), 2)

    # --- 2. 內聚性 (LCOM4) [模組內] ---
    def calculateCohesion(self, module_name: str) -> dict:
        """
        計算 LCOM4 (Lack of Cohesion of Methods version 4)。
        回傳: { 'ClassName': lcom4_score }
        LCOM4 = 1 (好), >1 (差，建議拆分)
        """
        graph = self.graphs.get(module_name)
        if not graph: return {}

        results = {}
        # 篩選出所有類別節點
        class_nodes = [d for _, d in graph.graph.nodes(data=True) if d.get('type') == 'class']

        for cls in class_nodes:
            cls_name = cls.get('name')

            # A. 找出該類別的所有方法
            methods = []
            method_usage = defaultdict(set) # {method_name: {fields...}}

            for _, d in graph.graph.nodes(data=True):
                # 找出屬於此類別的方法節點
                if d.get('type') == 'function' and d.get('parent_class') == cls_name:
                    methods.append(d.get('name'))

                # 找出屬於此類別的方法內部的「屬性存取」
                # (這依賴 PythonSourceAnalyzer 已經將 accessed_fields 寫入節點)
                if d.get('parent_class') == cls_name and d.get('parent_method'):
                    fields = d.get('accessed_fields', [])
                    for f in fields:
                        method_usage[d.get('parent_method')].add(f)

            if not methods:
                results[cls_name] = 1 # 無方法類別視為內聚 (或忽略)
                continue

            # B. 建立方法關聯圖 (Method Graph)
            m_graph = nx.Graph()
            m_graph.add_nodes_from(methods) # 確保孤立方法也被計入

            for i in range(len(methods)):
                for j in range(i + 1, len(methods)):
                    m1, m2 = methods[i], methods[j]
                    # 如果兩個方法使用了至少一個共同屬性，則連線
                    if not method_usage[m1].isdisjoint(method_usage[m2]):
                        m_graph.add_edge(m1, m2)

            # C. 計算連通分量數量
            lcom4 = nx.number_connected_components(m_graph)
            results[cls_name] = lcom4

        return results

    # --- 3. 程式碼行數 (LOC) [函式內] ---
    def calculateLOC(self, module_name: str) -> dict:
        """
        計算函式長度。
        回傳: { 'func_name': lines_of_code }
        """
        graph = self.graphs.get(module_name)
        if not graph: return {}

        results = {}
        for _, d in graph.graph.nodes(data=True):
            if d.get('type') == 'function':
                # 利用 AST 節點的 lineno 資訊
                start = d.get('lineno', 0)
                end = d.get('end_lineno', start)
                loc = end - start + 1
                # 排除單行定義的極端情況
                if loc < 0: loc = 0
                results[d.get('name')] = loc
        return results

    # --- 4. 穩定性 (Instability) [模組間] ---
    def calculateInstability(self, module_name: str) -> float:
        """
        計算穩定性指標 I。
        公式: I = Ce / (Ca + Ce)
        範圍: [0, 1]。0=穩定(負責被依賴), 1=不穩定(負責變更)
        """
        if module_name not in self.graphs: return 0.0

        # Ce (Efferent): 我依賴了誰 (Outgoing)
        ce = len(self.dependencies[module_name])

        # Ca (Afferent): 誰依賴了我 (Incoming)
        # 這需要遍歷全域依賴表
        ca = 0
        for other_mod, imports in self.dependencies.items():
            if other_mod != module_name and module_name in imports:
                ca += 1

        if (ca + ce) == 0:
            return 0.5 # 既不依賴人也沒人依賴，中性

        return round(ce / (ca + ce), 2)

    # --- 5. 抽象度 (Abstractness) [模組內] ---
    def calculateAbstractness(self, module_name: str) -> float:
        """
        計算抽象度 A。
        公式: A = 抽象類別數 / 總類別數
        範圍: [0, 1]
        """
        graph = self.graphs.get(module_name)
        if not graph: return 0.0

        total_classes = 0
        abstract_classes = 0

        for _, d in graph.graph.nodes(data=True):
            if d.get('type') == 'class':
                total_classes += 1
                # 檢查前置步驟中提取的 is_abstract 標記
                if d.get('is_abstract', False):
                    abstract_classes += 1

        if total_classes == 0:
            return 0.0

        return round(abstract_classes / total_classes, 2)


import tempfile
import shutil
import textwrap

# 假設上面已經定義了:
# 1. ASTGraph
# 2. PythonSourceAnalyzer
# 3. StructureAnalyzer

def run_demo():
    print("=== StructureAnalyzer 整合測試範例 ===\n")

    # 1. 建立暫存的測試專案環境
    test_dir = tempfile.mkdtemp(prefix="ast_demo_project_")
    print(f"[*] 建立測試專案目錄: {test_dir}")

    try:
        # --- 檔案 A: abstract_def.py (高抽象度，零依賴) ---
        # 包含一個抽象類別，沒有實作，沒有 import 其他內部模組
        code_a = textwrap.dedent("""
            from abc import ABC, abstractmethod

            class DataInterface(ABC):
                @abstractmethod
                def load(self):
                    pass

                @abstractmethod
                def save(self, data):
                    pass
        """)
        with open(os.path.join(test_dir, "abstract_def.py"), "w", encoding="utf-8") as f:
            f.write(code_a)

        # --- 檔案 B: utils.py (混合內聚性) ---
        # 包含兩個類別：
        # GoodCohesion: 方法間共享屬性 (LCOM4=1)
        # BadCohesion: 方法各做各的，屬性不共享 (LCOM4=2)
        code_b = textwrap.dedent("""
            class GoodCohesion:
                def __init__(self):
                    self.shared_data = []

                def add(self, item):
                    self.shared_data.append(item)

                def show(self):
                    print(self.shared_data)

            class BadCohesion:
                def __init__(self):
                    self.x = 0
                    self.y = 0

                def handle_x(self):
                    print(self.x)

                def handle_y(self):
                    print(self.y)
        """)
        with open(os.path.join(test_dir, "utils.py"), "w", encoding="utf-8") as f:
            f.write(code_b)

        # --- 檔案 C: main_controller.py (高耦合，高不穩定性) ---
        # Import 了上述兩個模組，屬於具體實作 (低抽象)
        code_c = textwrap.dedent("""
            import abstract_def
            import utils

            def main_logic():
                # 這裡使用了 utils
                helper = utils.GoodCohesion()
                helper.add("test")
                helper.show()

                # 這裡使用了 abstract_def
                print("Logic running...")

            def another_long_function():
                a = 1
                b = 2
                c = a + b
                print(c)
                # 佔位符，增加 LOC
                return c
        """)
        with open(os.path.join(test_dir, "main_controller.py"), "w", encoding="utf-8") as f:
            f.write(code_c)

        # 2. 初始化分析器
        print("[*] 開始分析原始碼...\n")
        analyzer = StructureAnalyzer(test_dir)

        # 3. 輸出報表
        headers = [
            "Module",
            "Coupling(Score)",
            "Instability(I)",
            "Abstract(A)",
            "LCOM4 (By Class)",
            "LOC (By Func)"
        ]
        # 格式化字串
        row_format = "{:<20} | {:<15} | {:<14} | {:<11} | {:<25} | {:<20}"

        print(row_format.format(*headers))
        print("-" * 115)

        for mod_name in sorted(analyzer.graphs.keys()):
            # 取得各項指標
            coup_score = analyzer.calculateCoupling(mod_name)
            instability = analyzer.calculateInstability(mod_name)
            abstractness = analyzer.calculateAbstractness(mod_name)
            lcom_dict = analyzer.calculateCohesion(mod_name)
            loc_dict = analyzer.calculateLOC(mod_name)

            # 簡化顯示用字串
            lcom_str = str(lcom_dict).replace("'", "") if lcom_dict else "-"
            loc_str = str(loc_dict).replace("'", "") if loc_dict else "-"

            print(row_format.format(
                mod_name,
                f"{coup_score:.1f}",
                f"{instability:.2f}",
                f"{abstractness:.2f}",
                lcom_str[:25] + "..." if len(lcom_str)>25 else lcom_str,
                loc_str[:20] + "..." if len(loc_str)>20 else loc_str
            ))

        print("-" * 115)
        print("\n=== 結果解讀 ===")
        print("1. [abstract_def]:   Abstract=1.00 (純介面), Instability=0.00 (非常穩定, 無依賴).")
        print("2. [utils]:          LCOM4 顯示 BadCohesion 為 2 (表示應拆分), GoodCohesion 為 1 (良好).")
        print("3. [main_controller]:Coupling 分數較低 (因依賴了2個模組), Instability=1.00 (非常不穩定, 依賴他人).")

    finally:
        # 4. 清理環境
        shutil.rmtree(test_dir)
        print(f"\n[*] 已移除測試目錄: {test_dir}")

if __name__ == "__main__":
    run_demo()
