import tkinter as tk
from tkinter import ttk
import os
import json

class ProjectExplorer:
    def __init__(self, parent, mediator):
        self.mediator = mediator # MainWindow
        self.meta = mediator.meta # MetaCoder

        self.frame = ttk.LabelFrame(parent, text="Project Explorer")

        self.tree = ttk.Treeview(self.frame)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Button-3>", self.show_context_menu)

        self._init_menu()

    def _init_menu(self):
        self.menu = tk.Menu(self.frame, tearoff=0)
        self.menu.add_command(label="Refine Module", command=self.on_refine)
        self.menu.add_command(label="Implement Function", command=self.on_implement)
        self.menu.add_command(label="Chaos Test", command=self.on_chaos)

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        data = self.meta.get_project_tree()
        if not data: return

        root = self.tree.insert("", "end", text=data.get('project_name', 'Project'), open=True)
        for mod in data.get('modules', []):
            mod_node = self.tree.insert(root, "end", text=mod['name'], open=True, values=("module",))
            # 這裡可以加入更詳細的 spec 讀取邏輯

    def on_select(self, event):
        item = self.tree.selection()[0]
        # 通知 WorkSpace 顯示代碼
        # 這裡簡化處理，實際應讀取檔案內容傳遞
        func_name = self.tree.item(item, "text")
        # self.mediator.workspace.show_code(...)

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.menu.post(event.x_root, event.y_root)

    def on_refine(self):
        item = self.tree.selection()[0]
        mod_name = self.tree.item(item, "text")

        def task():
            self.mediator.log(f"Refining {mod_name}...")
            # self.meta.refine_module(mod_name) ...
            # 模擬耗時
            import time; time.sleep(1)
            self.frame.after(0, self.refresh_tree)

        self.mediator.run_async(task)

    def on_implement(self):
        pass # 實作邏輯同前

    def on_chaos(self):
        pass # 實作邏輯同前
