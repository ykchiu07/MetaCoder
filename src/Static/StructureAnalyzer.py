import ast
import os
import glob
import math

import ASTGraph, PythonSourceParser

class StructureAnalyzer:
    """
    StructureAnalyzer: 專注於分析專案結構與模組耦合度的評估工具。
    """
    def __init__(self, decay_constant: float = 0.2):
        """
        Args:
            decay_constant (float): 指數遞減常數 (lambda)。
                                    數值越大，對耦合的懲罰越重，分數下降越快。
        """
        self.decay_constant = decay_constant

# --- 新增輔助方法 1: 建立內部模組清單 ---
    def _get_internal_modules(self, work_dir: str) -> set:
        """
        掃描工作目錄，找出屬於該專案的頂層模組名稱 (檔案或套件)。
        這將作為判斷 '是否為內部引用' 的基準。
        """
        internal_modules = set()
        try:
            for name in os.listdir(work_dir):
                full_path = os.path.join(work_dir, name)

                # 情況 A: 是一個 .py 檔案 (排除 __init__.py)
                if os.path.isfile(full_path) and name.endswith('.py') and name != '__init__.py':
                    internal_modules.add(name[:-3]) # 移除 .py 副檔名

                # 情況 B: 是一個含有 __init__.py 的目錄 (Python Package)
                elif os.path.isdir(full_path) and os.path.exists(os.path.join(full_path, '__init__.py')):
                    internal_modules.add(name)
        except OSError:
            pass
        return internal_modules

    # --- 新增輔助方法 2: 判斷是否為內部引用 ---
    def _is_internal_import(self, import_stmt_str: str, internal_modules: set) -> bool:
        """
        解析 import 字串，判斷其目標是否在 internal_modules 清單中。
        """
        try:
            # 利用 ast 解析這句單獨的 import 程式碼
            tree = ast.parse(import_stmt_str)
            for node in ast.walk(tree):
                # 處理 import x.y
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root_pkg = alias.name.split('.')[0] # 取最上層名稱
                        if root_pkg in internal_modules:
                            return True

                # 處理 from x import y (包含相對路徑 from . import y)
                elif isinstance(node, ast.ImportFrom):
                    # 如果 level > 0 (例如 from . import x)，絕對是內部引用
                    if node.level > 0:
                        return True
                    # 如果是 from package import module
                    if node.module:
                        root_pkg = node.module.split('.')[0]
                        if root_pkg in internal_modules:
                            return True
        except:
            # 若解析失敗則保守地視為非內部引用
            return False
        return False

    def calculate_coupling_score(self, import_count: int) -> float:
        """
        根據耦合數量計算評分 (0-100)。
        公式: Score = 100 * e^(-lambda * count)
        這符合「評分隨耦合度增加而指數遞減」的要求。
        """
        return 100.0 * math.exp(-self.decay_constant * import_count)

    def analyze_directory(self, work_dir: str) -> dict:
        results = {}

        # 1. 預先取得該目錄下的「內部模組白名單」
        internal_modules = self._get_internal_modules(work_dir)

        # 遞迴搜尋所有 .py 檔案
        pattern = os.path.join(work_dir, "**", "*.py")
        files = glob.glob(pattern, recursive=True)

        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source_code = f.read()

                # 建構 AST 圖
                graph = ASTGraph()
                analyzer = PythonSourceAnalyzer(graph)
                analyzer.analyze_code(source_code)

                # 2. 計算耦合度 (僅計算內部引用)
                internal_coupling_count = 0

                # 遍歷圖中所有節點
                for _, data in graph.graph.nodes(data=True):
                    # 篩選 import 類型的節點
                    if data.get('type') == 'import':
                        # 取得節點上的文字內容 (例如 "import utils")
                        import_content = data.get('label', '')

                        # 判斷是否為內部模組
                        if self._is_internal_import(import_content, internal_modules):
                            internal_coupling_count += 1

                # 計算評分 (使用內部引用數量)
                score = self.calculate_coupling_score(internal_coupling_count)

                results[file_path] = {
                    'coupling_count': internal_coupling_count, # 這裡只顯示內部耦合數
                    'score': round(score, 2)
                }

            except Exception as e:
                # print(f"Error analyzing {file_path}: {e}") # Debug 用
                results[file_path] = {'error': str(e)}

        return results

# --- 使用範例 ---
if __name__ == "__main__":
    # 假設當前目錄下有一些 Python 檔案
    # 您可以建立一個測試檔案來驗證
    analyzer = StructureAnalyzer(decay_constant=0.15)

    # 分析當前目錄 (.)
    analysis_report = analyzer.analyze_directory(".")

    print(f"{'Module Path':<40} | {'Imports':<8} | {'Score':<6}")
    print("-" * 60)
    for path, data in analysis_report.items():
        if 'error' not in data:
            print(f"{os.path.basename(path):<40} | {data['coupling_count']:<8} | {data['score']:<6}")
