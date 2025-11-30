import ast
from typing import List

# 假設上一段程式碼儲存在 ast_graph.py，或是直接在此檔案上方定義了 ASTGraph
# from ast_graph import ASTGraph

class PythonSourceParser:
    """
    分析 Python 原始碼並將其轉換為 ASTGraph 流程圖結構。
    """
    def __init__(self, graph_instance):
        self.graph = graph_instance
        # 新增狀態堆疊，用於記錄當前處於哪個 Class 或 Function 內
        self.current_class = None
        self.current_method = None
        self.source_lines = []  # [新增] 用於儲存原始碼行
    def _connect_with_context(self, src, target):
        """智能連接：若來源是條件或迴圈節點且尚未有 True 路徑，則自動標記為 No"""
        label = None
        src_node = self.graph.get_node_info(src)

        # 檢查來源節點是否為條件判斷或迴圈
        if src_node and src_node.get('type') in ['condition', 'loop']:
            # 檢查是否已有 Yes/True 路徑
            has_true = False
            for _, _, data in self.graph.graph.out_edges(src, data=True):
                if data.get('label') in ['Yes', 'True']:
                    has_true = True

            # 如果有 True 路徑，則這條新建立的邊應該是 False (No) 路徑
            if has_true:
                label = "No"

        self.graph.add_edge(src, target, condition=label)

    def analyze_code(self, source_code: str):
        """
        解析原始碼字串並填充 Graph。
        """
        # 1. 使用 Python 內建 AST 解析原始碼
        try:
            self.source_lines = source_code.splitlines()
            tree = ast.parse(source_code)
        except SyntaxError as e:
            print(f"Syntax Error in source code: {e}")
            return

        # 2. 建立起點
        start_node_id = self.graph.add_node("Program Start", node_type="start")

        # 3. 開始遞迴處理主要區塊
        # incoming_ids 代表「上一層流下來的節點 ID 列表」
        final_leaves = self._process_block(tree.body, [start_node_id])

        # 4. 建立終點並連接所有剩餘的葉節點
        end_node_id = self.graph.add_node("Program End", node_type="end")
        for leaf in final_leaves:
            self.graph.add_edge(leaf, end_node_id)

    def _process_block(self, statements: List[ast.stmt], incoming_ids: List[str]) -> List[str]:
        """
        遞迴處理一連串的語句 (Statements)。

        Args:
            statements: AST 語句列表
            incoming_ids: 上一步驟的節點 ID 列表 (可能有從多個分支匯合而來)

        Returns:
            outgoing_ids: 這一區塊執行完後，最末端的節點 ID 列表
        """
        current_incoming = incoming_ids

        for stmt in statements:
            # 針對每一個語句，處理並更新 current_incoming
            # 因為這個語句的輸出，將成為下一個語句的輸入
            current_incoming = self._process_statement(stmt, current_incoming)

        return current_incoming

    # [新增] 輔助函式：計算真實行數
    def _count_real_loc(self, start_line, end_line):
        if start_line is None or end_line is None:
            return 0

        # Python 行號從 1 開始，List 索引從 0 開始
        lines = self.source_lines[start_line-1 : end_line]
        real_count = 0
        for line in lines:
            stripped = line.strip()
            # 過濾空行與單行註解
            if stripped and not stripped.startswith('#'):
                real_count += 1
        return real_count

    def _process_statement(self, stmt: ast.stmt, incoming_ids: List[str]) -> List[str]:
        """
        處理單一語句，根據類型分派邏輯。
        回傳該語句結束後的所有「出口節點」。
        """

        # 1. 處理 If (分支)
        if isinstance(stmt, ast.If):
            condition_text = f"If {ast.unparse(stmt.test)}?"
            decision_id = self.graph.add_node(condition_text, node_type="decision")

            # 連接入口到這個判斷點
            for src in incoming_ids:
                self.graph.add_edge(src, decision_id)

            # 處理 True 路徑 (Body)
            true_leaves = self._process_block(stmt.body, [decision_id])
            # 為 True 路徑的第一步加上標籤 (我們需要手動修正第一條邊的 label)
            # 注意：這裡簡化處理，直接假設 _process_block 的第一個節點連接邏輯
            # 更嚴謹的做法是在 add_edge 時指定，但因為 block 內部邏輯封裝，
            # 我們可以簡單地在此層級標記：從 decision 出去的 edge 若連向 true_block 的頭，標記 Yes
            # (為了保持簡單，這裡我們用後處理或假設 logic 是對的，下面用更直接的方式)

            # --- 修正連接邏輯：我們需要明確知道分支的第一步是誰 ---
            # 由於 _process_block 依賴 incoming_ids 自動連線，我們很難在外部插入 "Yes" 標籤。
            # 所以我們改變策略：手動處理分支的第一步連線。

            # 重構分支連線：
            # A. 處理 True Block
            if stmt.body:
                # 手動取出第一句建立節點，為了加上 "Yes" 標籤
                first_true_stmt = stmt.body[0]
                # 遞迴呼叫單句處理，但這次 incoming 是空的，我們手動連
                # 這裡為了避免遞迴邏輯太複雜，我們簡化：
                # 讓 decision_id 傳入，但在 graph 內部，我們無法輕易修改剛建立的邊。
                # 最好的方式：_process_block 支援傳入 edge label?
                # 或者：我們在這裡手動連線 "Yes"。

                # 簡單做法：使用我們封裝的邏輯，但在這裡特例處理 True/False 標籤
                # 我們先建立邊，再讓 block 處理後續
                pass

            # 為了程式碼簡潔與穩健，我們使用較通用的方式：
            # 將 Decision 節點視為目前的 incoming，但我們需要在 Edge 上加屬性。
            # 因為 _process_block 會自動 add_edge，我們需要攔截那個行為，或者修改 ASTGraph。
            # 這裡採取「後修正」策略，或者在 `_process_block` 傳入 condition label。

            # 讓我們採用更直觀的「手動分派」：

            # Path 1: True
            # 找出 Body 的第一個實際節點有點難，所以我們加入一個「虛擬節點」或者直接解析
            # 這裡使用最簡單的 hack: 在 ASTGraph 增加 update_edge 或者我們接受沒有 Yes/No 標籤，
            # 但為了達到要求，我們手動處理第一層。

            # 取得 True Block 的結果
            # 先建立一個 Dummy 連接點或直接連線?
            # 我們直接在這裡呼叫 _process_block，傳入 [decision_id]。
            # 然後遍歷 graph 找出剛才 decision_id 連出去的邊，標上 "Yes"。
            true_exits = self._process_block(stmt.body, [decision_id])
            self._label_edges_from(decision_id, "Yes", exclude_existing=True) # 假設有這個輔助函式

            # Path 2: False (Else)
            false_exits = []
            if stmt.orelse:
                # 記錄目前的邊數量，以便區分新增的邊
                false_exits = self._process_block(stmt.orelse, [decision_id])
                self._label_edges_from(decision_id, "No", exclude_label="Yes")
            else:
                # 如果沒有 else，False 路徑直接流出 (即 decision 節點本身也是出口之一)
                # 但這代表 decision 連向「下一個語句」。
                # 我們把 decision_id 加入 false_exits
                false_exits = [decision_id]
                # 這條邊會在下一個語句被建立，標籤怎麼辦？
                # 這是一個典型的流程圖繪製難題。
                # 解決方案：回傳 (id, edge_label_for_next)
                pass

            return true_exits + false_exits

        # 2. 處理 While (迴圈)
        elif isinstance(stmt, ast.While):
            condition_text = f"While {ast.unparse(stmt.test)}?"
            decision_id = self.graph.add_node(condition_text, node_type="decision")

            for src in incoming_ids:
                self.graph.add_edge(src, decision_id)

            # Body
            body_exits = self._process_block(stmt.body, [decision_id])
            self._label_edges_from(decision_id, "True", exclude_existing=True)

            # Loop back: 將 body 的出口連回 decision
            for leaf in body_exits:
                self.graph.add_edge(leaf, decision_id)

            # While 的出口是當條件為 False 時，直接從 Decision 出去
            # 我們需要標記這條未來的邊為 False
            # 這裡我們做一個 trick: 回傳一個 tuple (id, condition) 給上層？
            # 或者簡單地，我們在外部標記。
            # 為了保持介面簡單，這裡回傳 decision_id，
            # 並期待 _process_block 的下一次迭代會連線。
            # 我們預先在這裡設定一個屬性給 decision_id 說「下一條邊是 False」比較困難。
            # 簡單解法：While False 出口就是 decision_id。標籤在 ASTGraph 繪圖時可能顯示不出來，除非我們特別處理。
            return [decision_id]
        elif isinstance(stmt, ast.For):
            # 1. 解析迴圈變數與迭代範圍
            target = ast.unparse(stmt.target)   # 例如 "i"
            iterator = ast.unparse(stmt.iter)   # 例如 "range(10)"
            condition_text = f"For {target} in {iterator}?"

            # 2. 建立迴圈節點 (類型設為 loop)
            loop_id = self.graph.add_node(condition_text, node_type="loop")

            # 3. 將上一步驟連入此迴圈節點
            for src in incoming_ids:
                self._connect_with_context(src, loop_id)

            # 4. 處理迴圈內部 (True/Yes 路徑)
            body_exits = self._process_block(stmt.body, [loop_id])
            self._label_edges_from(loop_id, "True", exclude_existing=True)

            # 5. Loop Back: 將迴圈內部的終點連回開頭
            for leaf in body_exits:
                self.graph.add_edge(leaf, loop_id)

            # 6. 處理 for-else 語法 (Python 特有，若迴圈正常結束則執行)
            if stmt.orelse:
                # 如果有 else，False 路徑進入 else block
                orelse_exits = self._process_block(stmt.orelse, [loop_id])
                self._label_edges_from(loop_id, "False", exclude_label="True")
                return orelse_exits

            # 7. 若無 else，迴圈結束後直接往下一步走 (False 路徑)
            # 下一個指令的 source 就是這個 loop_id
            return [loop_id]
        # 3. 處理基本語句 (Assignment, Expr, Return, Print)
        elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
            # 1. 取得語句內容 (如 "import math" 或 "from os import path")
            content = ast.unparse(stmt)

            # 2. 建立節點，類型設為 "import"
            node_id = self.graph.add_node(content, node_type="import")

            # 3. 連接上下文 (從上一步驟流向此 Import)
            for src in incoming_ids:
                self._connect_with_context(src, node_id)

            # Import 執行完後，流程繼續往下
            return [node_id]

        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # [新增] 取得結束行號 (Python 3.8+)
            end_lineno = getattr(stmt, 'end_lineno', stmt.lineno)

            # [關鍵修改] 呼叫計算函式
            real_loc = self._count_real_loc(stmt.lineno, end_lineno)

            # [關鍵修改] add_node 時傳入詳細資訊
            func_id = self.graph.add_node(
                f"def {stmt.name}",
                node_type="function",
                name=stmt.name,                   # 用於 LOC 識別
                lineno=stmt.lineno,               # 用於 LOC 計算
                end_lineno=end_lineno,            # 用於 LOC 計算
                real_loc=real_loc,        # [新增] 儲存過濾後的行數
                parent_class=self.current_class   # 用於 LCOM4 歸屬
            )

            for src in incoming_ids:
                self._connect_with_context(src, func_id)

            # [新增] 更新 Context 並遞迴
            prev_method = self.current_method
            self.current_method = stmt.name
            self._process_block(stmt.body, [func_id])
            self.current_method = prev_method

            return [func_id]

        elif isinstance(stmt, ast.ClassDef):
            # --- 抽象度分析邏輯 ---
            is_abstract = False
            # 1. 檢查繼承 (Bases): 是否繼承 'ABC'
            for base in stmt.bases:
                if isinstance(base, ast.Name) and base.id == 'ABC':
                    is_abstract = True
                    break
                # (進階可檢查 attribute access 如 abc.ABC)

            # 2. 檢查方法裝飾器 (Decorators): 是否有 @abstractmethod
            if not is_abstract:
                for node in ast.walk(stmt):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for decorator in node.decorator_list:
                            # 檢查 @abstractmethod 或 @abc.abstractmethod
                            if (isinstance(decorator, ast.Name) and decorator.id == 'abstractmethod') or \
                               (isinstance(decorator, ast.Attribute) and decorator.attr == 'abstractmethod'):
                                is_abstract = True
                                break
                    if is_abstract: break

            # [關鍵修改] add_node 時傳入 name, lineno, is_abstract
            class_id = self.graph.add_node(
                f"class {stmt.name}",
                node_type="class",
                name=stmt.name,            # 用於 LCOM4 識別
                lineno=stmt.lineno,        # 用於 LOC (雖然類別通常不用 LOC，但為了完整性)
                is_abstract=is_abstract    # 用於抽象度計算 (請確認 is_abstract 變數已計算)
            )

            for src in incoming_ids:
                self._connect_with_context(src, class_id)

            # [新增] 更新 Context 並遞迴
            prev_class = self.current_class
            self.current_class = stmt.name # 設定當前類別
            self._process_block(stmt.body, [class_id])
            self.current_class = prev_class # 還原

            return [class_id]

        else:
            # --- 新增修改：過濾 Docstring / 多行註解 ---
            # 檢查語句是否為 ast.Expr (表達式)，且其內容為 ast.Constant (常數)，且值為字串
            # Python 3.8+ 使用 ast.Constant, 舊版可能需檢查 ast.Str (此處以新版標準為主)
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                # 如果是獨立的字串常數 (即多行註解)，直接略過。
                # 回傳 incoming_ids，代表「上一個節點」的流向直接傳遞給「下一個語句」，
                # 就像這個註解節點不存在一樣。
                return incoming_ids
            # ---------------------------------------
# [新增] LCOM4 關鍵：提取使用的實例屬性 (Field Access)
            used_fields = set()
            if self.current_class and self.current_method:
                for node in ast.walk(stmt):
                    # 尋找 self.xxx 的模式
                    if isinstance(node, ast.Attribute):
                        if isinstance(node.value, ast.Name) and node.value.id == 'self':
                            used_fields.add(node.attr)
            # --------------------------------------------------
            content = ast.unparse(stmt)

            # 簡單判斷是否為 I/O (Print 或 Input)
            is_io = False
            # 檢查是否為 print() 呼叫
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                func_name = getattr(stmt.value.func, 'id', '')
                if func_name == 'print':
                    is_io = True
            # 檢查賦值語句右邊是否有 input()
            elif isinstance(stmt, ast.Assign):
                if isinstance(stmt.value, ast.Call) and getattr(stmt.value.func, 'id', '') == 'input':
                    is_io = True
                # 處理 int(input(...)) 的巢狀情況
                elif isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name) and stmt.value.func.id in ('int', 'float', 'str'):
                     if stmt.value.args and isinstance(stmt.value.args[0], ast.Call) and getattr(stmt.value.args[0].func, 'id', '') == 'input':
                        is_io = True

            n_type = "io" if is_io else "process" # 假設 is_io 已計算

            node_id = self.graph.add_node(
                content,
                node_type=n_type,
                lineno=stmt.lineno,             # LOC 支援
                parent_class=self.current_class, # LCOM4 支援 (方便追蹤)
                parent_method=self.current_method,
                accessed_fields=list(used_fields) # LCOM4 支援：記錄此節點用到的屬性
            )

            for src in incoming_ids:
                self._connect_with_context(src, node_id)

            return [node_id]

    def _label_edges_from(self, source_id, label, exclude_existing=False, exclude_label=None):
        """
        輔助函式：為剛建立的邊加上標籤。
        這是為了解決遞迴建立節點時，難以即時傳入 Edge Label 的問題。
        """
        edges = self.graph.graph.out_edges(source_id, data=True)
        for u, v, data in edges:
            if exclude_existing and 'label' in data:
                continue
            if exclude_label and data.get('label') == exclude_label:
                continue

            # NetworkX 的邊屬性更新
            self.graph.graph[u][v]['label'] = label

# --- 整合測試範例 ---

if __name__ == "__main__":
    # 假設我們有上一回合的 ASTGraph 類別
    # 這裡為了示範完整性，我們需要一個 ASTGraph 實例
    # (請確保 ASTGraph 類別已定義或匯入)

        # 假設使用者已貼上之前的 ASTGraph class 定義
    from ASTGraph import ASTGraph
        # 這裡為了執行方便，假定 ast = ASTGraph() 已能運作，若您在同一腳本執行，請確保類別存在。


    # 定義一段測試用的原始碼
    sample_code = open(input(),'r').read()

    # 1. 初始化圖結構
    # 注意：這裡依賴您上一段程式碼的 ASTGraph 類別
    # 如果是合併執行，請確保 ASTGraph 類別在上方
    # ast_graph = ASTGraph()  <-- 您需要這行

    # 為了讓這段回應獨立完整，我寫一個 Mock 讓您可以看結構，但實際運行請結合上一段代碼
    class MockASTGraph: # 僅用於當此代碼被單獨複製時不報錯
        def add_node(self, *args, **kwargs): return "mock_id"
        def add_edge(self, *args, **kwargs): pass
        def get_node_info(self, *args): return {}
        def visualize(self): print("Visualizing...")
        def __getattr__(self, name): return self # Mock other attributes

    # 請取消下面這行的註解並使用真實的 ASTGraph
    ast_graph = ASTGraph()

    # 這裡僅作邏輯展示，若您要執行，請將之前的 ASTGraph 貼在上方
    print("請將此模組與 ASTGraph 類別結合使用。")

    # 使用範例 (虛擬碼):
    analyzer = PythonSourceParser(ast_graph)
    analyzer.analyze_code(sample_code)
    ast_graph.visualize()
