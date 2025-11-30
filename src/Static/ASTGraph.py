import networkx as nx
import matplotlib.pyplot as plt
import uuid

class ASTGraph:
    """
    ASTGraph: 用於儲存虛擬碼流程圖的資料結構。
    基於 NetworkX 的 DiGraph (有向圖) 實作。
    """

    def __init__(self):
        # 初始化一個有向圖
        self.graph = nx.DiGraph()
        # 記錄起始節點 ID (可選)
        self.root_id = None

# 修改原本的 add_node，增加 **kwargs
    def add_node(self, content: str, node_type: str = "process", node_id: str = None, **kwargs) -> str:
        if node_id is None:
            node_id = str(uuid.uuid4())[:8]

        # [修改點] 確保將 kwargs 傳遞給 NetworkX 的 add_node
        # 原本可能是: self.graph.add_node(node_id, label=content, type=node_type)
        self.graph.add_node(node_id, label=content, type=node_type, **kwargs)

        if self.root_id is None:
            self.root_id = node_id

        return node_id

    def add_edge(self, source_id: str, target_id: str, condition: str = None):
        """
        建立兩個節點之間的流向 (邊)。

        Args:
            source_id (str): 來源節點 ID
            target_id (str): 目標節點 ID
            condition (str, optional): 邊的標籤 (例如: "Yes", "No", "True")，用於判斷式分支。
        """
        if source_id not in self.graph or target_id not in self.graph:
            raise ValueError("Source or Target ID does not exist in the graph.")

        # NetworkX 允許在邊上儲存屬性
        attr = {}
        if condition:
            attr['label'] = condition

        self.graph.add_edge(source_id, target_id, **attr)

    def get_node_info(self, node_id: str) -> dict:
        """取得特定節點的詳細資訊"""
        if node_id in self.graph:
            return self.graph.nodes[node_id]
        return None

    def get_next_steps(self, node_id: str) -> list:
        """
        取得某節點的下一步驟 (Outgoing edges)。
        回傳格式: [(target_id, condition), ...]
        """
        successors = []
        # 遍歷該節點指出的所有邊
        for _, target, data in self.graph.out_edges(node_id, data=True):
            condition = data.get('label', None)
            successors.append((target, condition))
        return successors

    def visualize(self):
        plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'SimHei']
        #解決負號亂碼問題 (這是 CJK 字體常見的額外步驟)
        plt.rcParams['axes.unicode_minus'] = False
        """
        使用 Matplotlib 繪製流程圖。
        根據節點類型給予不同顏色與形狀。
        """
        if self.graph.number_of_nodes() == 0:
            print("Graph is empty.")
            return

        pos = nx.spring_layout(self.graph, seed=42, k=0.5, iterations=50)  # 節點佈局演算法
        plt.figure(figsize=(16, 10))
        # 1. 定義樣式映射
        color_map = []
        node_shapes = []
        labels = {}

        type_color = {
            'start': '#88d8b0',    # 綠色
            'end': '#ff6f69',      # 紅色
            'process': '#a8e6cf',  # 淺青
            'decision': '#ffeead', # 黃色 (菱形通常用於判斷，但在 nx 繪圖簡單處理用顏色區分)
            'io': '#dcedc1',       # 淺綠
            'import': '#e6e6fa',   # 淺紫色 (Lavender)，代表外部引入
            'function': '#97c2fc', # 淡藍色，用於函式定義
            'class': '#ffe156',    # 金黃色，用於類別定義
        }

        for node, data in self.graph.nodes(data=True):
            n_type = data.get('type', 'process')
            color_map.append(type_color.get(n_type, '#cccccc'))
            labels[node] = data.get('label', node)

        node_collection = nx.draw_networkx_nodes(self.graph, pos,
                                                 node_color=color_map,
                                                 node_size=2500,
                                                 alpha=0.9)

        # 手動設定節點的 Z-order (較低)
        if node_collection is not None:
            node_collection.set_zorder(2)

        # 2. 繪製節點標籤 (Labels) - 捕捉返回的 Text 對象
        # Note: 標籤在 Matplotlib 中是 Text 物件
        label_handles = nx.draw_networkx_labels(self.graph, pos, labels,
                                                font_size=9)

        # 手動設定標籤的 Z-order (略高於節點)
        if label_handles:
            for text_obj in label_handles.values():
                text_obj.set_zorder(3)

        # 3. 繪製邊和箭頭 (Edges) - 捕捉返回的 Collection 對象
        # 注意: 此處不再使用 zorder=... 參數
        edge_collection = nx.draw_networkx_edges(self.graph, pos,
                                                 edge_color='gray',
                                                 arrows=True,
                                                 arrowsize=20)

        # 手動設定邊和箭頭的 Z-order (最高，確保在節點之上)
        if edge_collection is not None:
           for edge in edge_collection:
               edge.set_zorder(4)

        # 5. 繪製邊上的文字 (True/False 等條件)
        edge_labels = nx.get_edge_attributes(self.graph, 'label')
        nx.draw_networkx_edge_labels(self.graph, pos, edge_labels=edge_labels, font_color='blue')

        plt.title("Pseudocode AST Graph Visualization")
        plt.axis('off')
        plt.show()

# --- 使用範例 ---

if __name__ == "__main__":
    # 1. 實例化
    ast = ASTGraph()

    # 2. 建立節點 (模擬一個簡單的迴圈程式)
    # Start -> Input n -> if n < 5 -> print "Small" -> End
    #                     else -> n = n - 1 (Loop back)

    start_node = ast.add_node("Start", node_type="start")
    input_node = ast.add_node("Input n", node_type="io")
    decision_node = ast.add_node("Is n < 5?", node_type="decision")
    process_true = ast.add_node("Print 'Small'", node_type="io")
    process_false = ast.add_node("n = n - 1", node_type="process")
    end_node = ast.add_node("End", node_type="end")

    # 3. 連接流程 (定義邊與條件)
    ast.add_edge(start_node, input_node)
    ast.add_edge(input_node, decision_node)

    # 分支：True
    ast.add_edge(decision_node, process_true, condition="Yes")
    ast.add_edge(process_true, end_node)

    # 分支：False (迴圈)
    ast.add_edge(decision_node, process_false, condition="No")
    ast.add_edge(process_false, decision_node) # 連回判斷點形成迴圈

    # 4. 存取測試
    print(f"Root Node ID: {ast.root_id}")
    print(f"Decision Node Next Steps: {ast.get_next_steps(decision_node)}")

    # 5. 視覺化
    # ast.visualize() # 若在 Jupyter Notebook 或本地環境可取消註解此行以查看圖形
