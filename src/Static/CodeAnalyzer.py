import radon.complexity as radon_cc
import radon.metrics as radon_metrics
import radon.raw as radon_raw
from radon.visitors import ComplexityVisitor

class CodeAnalyzer:
    """
    CodeAnalyzer: 專注於「程式碼層級」的指標計算。
    完全封裝 radon 套件，負責計算單一檔案或程式碼片段的統計數據。
    """
    def __init__(self, source_code: str):
        """
        Args:
            source_code (str): 待分析的原始碼字串。
        """
        self.code = source_code

    # --- 1. 迴圈複雜度 (Cyclomatic Complexity) ---
    def calculateComplexity(self) -> dict:
        """
        計算程式碼中每個函式/方法的圈複雜度 (CC)。

        Returns:
            dict: { 'function_name': cc_score (int) }
            若程式碼中無函式，則回傳空字典。
        """
        results = {}
        try:
            # cc_visit 會自動解析 AST 並找出所有區塊 (Function/Class)
            blocks = radon_cc.cc_visit(self.code)

            for block in blocks:
                # 只關注函式與方法 (Function & Method)
                # 若 block 是 Class，通常我們看它內部的方法
                if hasattr(block, 'type') and block.type in ('function', 'method'):
                    # 若有重名函式 (如不同類別中的同名方法)，這裡做簡單處理
                    # 實際應用可結合 lineno 作為 key
                    name = block.name
                    if hasattr(block, 'classname') and block.classname:
                        name = f"{block.classname}.{block.name}"

                    results[name] = block.complexity
        except Exception as e:
            print(f"[Radon CC Error]: {e}")

        return results

    # --- 2. Halstead 複雜度 (Halstead Metrics) ---
    def calculateHalstead(self) -> dict:
        """
        計算 Halstead 指標 (體積 Volume, 難度 Difficulty, 工作量 Effort)。
        這通常是針對整段傳入的代碼計算。
        """
        try:
            h_metrics = radon_metrics.h_visit(self.code)
            # h_visit 回傳的是一個 named tuple，包含 total 和 functions 屬性
            # 這裡我們回傳整體的統計
            return {
                'volume': round(h_metrics.total.volume, 2),
                'difficulty': round(h_metrics.total.difficulty, 2),
                'effort': round(h_metrics.total.effort, 2)
            }
        except Exception:
            # 可能是語法錯誤或空檔案
            return {'volume': 0, 'difficulty': 0, 'effort': 0}

    # --- 3. 原始碼統計 (Raw Metrics / SLOC) ---
    def calculateRawMetrics(self) -> dict:
        """
        計算 LOC (總行數), LLOC (邏輯行數), SLOC (原始碼行數 - 去除空行註解), Comments (註解行數)。
        """
        try:
            raw = radon_raw.analyze(self.code)
            return {
                'loc': raw.loc,           # Total lines
                'lloc': raw.lloc,         # Logical lines
                'sloc': raw.sloc,         # Source lines (Code only)
                'comments': raw.comments, # Comment lines
                'blank': raw.blank        # Blank lines
            }
        except Exception:
            return {'loc': 0, 'lloc': 0, 'sloc': 0, 'comments': 0, 'blank': 0}

    # --- 4. 維護性指標 (Maintainability Index) ---
    def calculateMaintainability(self) -> float:
        """
        計算維護性指標 (MI)。範圍 0-100，越高越好。
        < 65: 低 (難以維護)
        65-85: 中
        > 85: 高 (易於維護)
        """
        try:
            # multi=True 表示支援多行字串計算
            mi_score = radon_metrics.mi_visit(self.code, multi=True)
            return round(mi_score, 2)
        except Exception:
            return 0.0
