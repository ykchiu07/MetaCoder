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
        """掃描目錄建立內部模組白名單 (排除 tests)"""
        mods = set()
        for root, _, files in os.walk(work_dir):
            # [Fix 1] 排除測試目錄
            if "tests" in root.split(os.sep):
                continue

            for file in files:
                # [Fix 1] 排除測試檔案
                if file.endswith(".py") and file != "__init__.py" and not file.startswith("test_"):
                    rel_path = os.path.relpath(os.path.join(root, file), work_dir)
                    mod_name = rel_path.replace(os.sep, ".")[:-3]
                    mods.add(mod_name)
                    if "." in mod_name:
                        mods.add(mod_name.split('.')[0])
        return mods

    def _preprocess(self):
        """一次性解析所有檔案 (排除 tests)"""
        for root, _, files in os.walk(self.work_dir):
            # [Fix 1] 排除測試目錄
            if "tests" in root.split(os.sep):
                continue

            for file in files:
                if file.endswith(".py") and not file.startswith("test_"):
                    path = os.path.join(root, file)
                    rel_path = os.path.relpath(path, self.work_dir)
                    mod_name = rel_path.replace(os.sep, ".")[:-3]
                    if file == "__init__.py":
                        mod_name = rel_path.replace(os.sep, ".")[:-12]

                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            code = f.read()

                        graph = ASTGraph.ASTGraph()
                        analyzer = PythonSourceParser.PythonSourceParser(graph)
                        analyzer.analyze_code(code)
                        self.graphs[mod_name] = graph

                        # ... (依賴提取邏輯保持不變) ...
                        for _, data in graph.graph.nodes(data=True):
                            if data.get('type') == 'import':
                                imp_str = data.get('label', '')
                                for token in imp_str.replace(',', ' ').split():
                                    clean_token = token.split('.')[0]
                                    if clean_token in self.internal_modules and clean_token != mod_name:
                                        self.dependencies[mod_name].add(clean_token)
                    except Exception as e:
                        print(f"[Analyzer] Error processing {file}: {e}")

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
    # 修改 calculateCohesion
    def calculateCohesion(self, module_name: str) -> dict:
        """
        計算 LCOM4 與 連接密度 (Density)。
        Returns: { 'ClassName': {'lcom4': int, 'density': float} }
        """
        graph = self.graphs.get(module_name)
        if not graph: return {}

        results = {}
        class_nodes = [d for _, d in graph.graph.nodes(data=True) if d.get('type') == 'class']

        for cls in class_nodes:
            cls_name = cls.get('name')

            # 1. 建立方法關聯圖
            methods = []
            method_usage = defaultdict(set)

            for _, d in graph.graph.nodes(data=True):
                # 找出方法
                if d.get('type') == 'function' and d.get('parent_class') == cls_name:
                    methods.append(d.get('name'))
                # 找出屬性使用
                if d.get('parent_class') == cls_name and d.get('parent_method'):
                    fields = d.get('accessed_fields', [])
                    for f in fields:
                        method_usage[d.get('parent_method')].add(f)

            # 無方法或單一方法，視為完美內聚
            if len(methods) <= 1:
                results[cls_name] = {'lcom4': 1, 'density': 1.0}
                continue

            m_graph = nx.Graph()
            m_graph.add_nodes_from(methods)

            actual_edges = 0
            for i in range(len(methods)):
                for j in range(i + 1, len(methods)):
                    m1, m2 = methods[i], methods[j]
                    if not method_usage[m1].isdisjoint(method_usage[m2]):
                        m_graph.add_edge(m1, m2)
                        actual_edges += 1

            # 2. 計算 LCOM4 (連通分量數)
            lcom4 = nx.number_connected_components(m_graph)

            # 3. [新增] 計算連接密度 (Density)
            # Max Edges = n * (n-1) / 2
            n = len(methods)
            max_edges = (n * (n - 1)) / 2
            density = 0.0
            if max_edges > 0:
                density = round(actual_edges / max_edges, 2)

            results[cls_name] = {'lcom4': lcom4, 'density': density}

        return results

    # --- 3. 穩定性 (Instability) [模組間] ---
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

    # --- 4. 抽象度 (Abstractness) [模組內] ---
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


    # --- [新增] 虛擬靜態分析 (Phase 2 Check) ---
    def detect_cycles_from_stubs(self, virtual_code_map: dict) -> list:
        """
        基於虛擬代碼 map { 'mod_name': 'import a\nimport b' } 檢測循環依賴。
        Returns: list of cycles (e.g. [['a', 'b', 'a']])
        """
        temp_graph = nx.DiGraph()

        for mod, code in virtual_code_map.items():
            temp_graph.add_node(mod)
            # 簡單解析 import
            for line in code.splitlines():
                if line.startswith("import "):
                    target = line.split(" ")[1].strip()
                    temp_graph.add_edge(mod, target)
                elif line.startswith("from "):
                    parts = line.split(" ")
                    if len(parts) >= 2:
                        target = parts[1].strip().split('.')[0] # 取頂層模組
                        temp_graph.add_edge(mod, target)

        try:
            return list(nx.simple_cycles(temp_graph))
        except:
            return []

    # --- [新增] 實作一致性檢查 (Phase 3 Check) ---
    def verify_implementation_deps(self, code_path: str, allowed_deps: list) -> bool:
        """
        解析真實 Python 檔案，確認其 import 是否超出 allowed_deps 範圍。
        """
        try:
            with open(code_path, 'r', encoding='utf-8') as f:
                code = f.read()

            # 使用 ASTGraph 解析
            g = ASTGraph.ASTGraph()
            p = PythonSourceParser.PythonSourceParser(g)
            p.analyze_code(code)

            actual_imports = set()
            for _, data in g.graph.nodes(data=True):
                if data.get('type') == 'import':
                    label = data.get('label', '')
                    # 處理 "from x import y" 或 "import x"
                    # 簡化邏輯：抓第一個 token
                    token = label.replace("from ", "").replace("import ", "").split(" ")[0].split('.')[0]
                    actual_imports.add(token)

            # 檢查是否違反 (忽略標準庫，這裡假設 internal_modules 已正確填充)
            # 若 internal_modules 為空，需重新初始化
            if not self.internal_modules:
                self._preprocess()

            for imp in actual_imports:
                # 如果是專案內部的模組，但不在允許列表內 -> 違規
                if imp in self.internal_modules and imp not in allowed_deps:
                    # 排除自己
                    # 取得 code_path 所屬模組名...這裡簡化，假設呼叫者會處理
                    print(f"[Audit] Violation: Imported '{imp}' but only {allowed_deps} allowed.")
                    return False

            return True

        except Exception as e:
            print(f"[Audit Error] {e}")
            return False # 保守策略：分析失敗視為失敗
