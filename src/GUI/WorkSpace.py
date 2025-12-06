import tkinter as tk
from tkinter import ttk, scrolledtext

class WorkSpace:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        colors = mediator.colors

        self.frame = ttk.Frame(parent)

        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Code Editor (暗色配置)
        self.code_editor = scrolledtext.ScrolledText(
            self.notebook,
            font=("Consolas", 11),
            bg=colors['editor_bg'],
            fg="#a9b7c6",
            insertbackground="white", # 游標顏色
            selectbackground="#214283"
        )
        self.notebook.add(self.code_editor, text="Code Editor")

        # Tab 2: Graph
        self.canvas = tk.Canvas(self.notebook, bg="white") # 圖表通常還是白底比較清楚，或設為灰色
        self.notebook.add(self.canvas, text="Dependency Graph")

    # ...
