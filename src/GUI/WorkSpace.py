import tkinter as tk
from tkinter import ttk, scrolledtext
import math
import random

class WorkSpace:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        colors = mediator.colors

        self.frame = ttk.Frame(parent)

        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

        # Tab 1: Code Editor
        self.code_editor = scrolledtext.ScrolledText(
            self.notebook,
            font=("Consolas", 11),
            bg=colors['editor_bg'],
            fg="#a9b7c6",
            insertbackground="white",
            selectbackground="#214283"
        )
        self.notebook.add(self.code_editor, text="Code Editor")

        # Tab 2: Graph (暗色背景)
        self.canvas = tk.Canvas(self.notebook, bg=colors['editor_bg'], highlightthickness=0)
        self.notebook.add(self.canvas, text="Dependency Graph")

    def on_tab_change(self, event):
        selected_tab = self.notebook.index(self.notebook.select())
        if selected_tab == 1:
            self.draw_dependency_graph()

    def _generate_colors(self, n):
        """生成 n 個高對比度的顏色 (Pastel 風格適合暗色主題)"""
        colors = []
        for i in range(n):
            hue = i / n
            # HSL to RGB 簡單轉換
            # 這裡直接用預定義的一組好看顏色循環使用
            palette = [
                "#ff79c6", "#bd93f9", "#8be9fd", "#50fa7b", "#ffb86c", "#ff5555",
                "#f1fa8c", "#6272a4", "#4a88c7", "#e06c75", "#98c379", "#61afef"
            ]
            colors.append(palette[i % len(palette)])
        return colors

    def draw_dependency_graph(self):
        """
        繪製函式分佈圖 (Function Distribution Map)
        邏輯：
        1. 獲取 {Module: [Functions]}
        2. 每個 Module 分配一個顏色
        3. 將畫布分為 Module 數量的區域 (Sectors)
        4. 在該區域內隨機/規則排列 Function 節點
        5. 右下角繪製 Legend
        """
        self.canvas.delete("all")

        # 1. 獲取數據
        # 這裡改用新方法：獲取函式分佈
        data = self.mediator.meta.get_function_distribution()
        # data format: {'module_a': ['func1', 'func2'], 'module_b': ['f3']}

        if not data:
            self.canvas.create_text(
                400, 300,
                text="No functions analyzed. Try 'Run Diagnostics' or 'Static Eval' first.",
                fill="#666", font=("Arial", 14)
            )
            return

        modules = list(data.keys())
        colors = self._generate_colors(len(modules))
        mod_color_map = {mod: col for mod, col in zip(modules, colors)}

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width < 100: width = 800
        if height < 100: height = 600

        center_x, center_y = width / 2, height / 2
        # 半徑設定：留出邊距給 Legend 和邊框
        max_radius = min(width, height) / 2 - 50

        # 2. 繪製節點 (Function Nodes)
        # 採用極座標佈局：每個模組佔據一個角度區間
        total_modules = len(modules)
        angle_per_mod = (2 * math.pi) / total_modules if total_modules > 0 else 0

        for i, mod in enumerate(modules):
            funcs = data[mod]
            if not funcs: continue

            # 該模組的角度範圍
            start_angle = i * angle_per_mod
            end_angle = (i + 1) * angle_per_mod

            color = mod_color_map[mod]

            # 在扇形區域內分佈函式
            # 簡單做法：在該角度範圍內隨機擴散，距離圓心一定距離
            for j, func in enumerate(funcs):
                # 角度：在區間內稍微隨機，避免重疊成一條線
                # 加入一些隨機抖動
                theta = start_angle + (angle_per_mod * (j + 0.5) / len(funcs))
                # 半徑：隨機分佈在 20% ~ 90% 的 max_radius 之間
                r = max_radius * (0.3 + 0.6 * random.random())

                x = center_x + r * math.cos(theta)
                y = center_y + r * math.sin(theta)

                # 畫節點
                node_r = 8 # 節點半徑
                self.canvas.create_oval(
                    x - node_r, y - node_r, x + node_r, y + node_r,
                    fill=color, outline="white", width=1
                )

                # 畫文字 (函式名)
                self.canvas.create_text(
                    x, y + 15, text=func,
                    fill="#ccc", font=("Consolas", 8)
                )

        # 3. 繪製 Legend (圖例) - 右下角
        legend_x = width - 200
        legend_y = height - (len(modules) * 20) - 20

        # 半透明背景
        self.canvas.create_rectangle(
            legend_x - 10, legend_y - 10, width - 10, height - 10,
            fill="#222", outline="#444"
        )

        self.canvas.create_text(
            legend_x, legend_y - 20,
            text="[ Module Legend ]", fill="white", anchor="nw", font=("Arial", 9, "bold")
        )

        for i, mod in enumerate(modules):
            y_pos = legend_y + (i * 20)
            col = mod_color_map[mod]

            # 色塊
            self.canvas.create_rectangle(
                legend_x, y_pos, legend_x + 12, y_pos + 12,
                fill=col, outline=""
            )
            # 文字
            self.canvas.create_text(
                legend_x + 20, y_pos,
                text=mod, fill="#ccc", anchor="nw", font=("Consolas", 9)
            )

        # 顯示統計
        total_funcs = sum(len(f) for f in data.values())
        self.canvas.create_text(
            20, 20, anchor="nw",
            text=f"Total Functions: {total_funcs} | Modules: {len(modules)}",
            fill="#888", font=("Consolas", 10)
        )
