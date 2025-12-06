import tkinter as tk
from tkinter import ttk
import os
import json

class ProjectExplorer:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        self.meta = mediator.meta

        self.frame = ttk.LabelFrame(parent, text="Project Explorer")

        # 啟用多選模式 (selectmode="extended")
        self.tree = ttk.Treeview(self.frame, selectmode="extended")
        self.tree.pack(fill=tk.BOTH, expand=True)

        # 綁定事件
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Button-3>", self.show_context_menu)

        self._init_menu()

    def _init_menu(self):
        self.menu = tk.Menu(self.frame, tearoff=0)
        self.menu.add_command(label="Refine Selected Modules (Phase 2)", command=self.on_refine)
        self.menu.add_command(label="Implement Selected Functions (Phase 3)", command=self.on_implement)
        self.menu.add_separator()
        self.menu.add_command(label="Show Architecture JSON", command=self.show_arch_json)

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        data = self.meta.get_project_tree()
        if not data: return

        # 根節點標記 type=project
        root = self.tree.insert("", "end", text=data.get('project_name', 'Project'), open=True, values=("project",))

        for mod in data.get('modules', []):
            # 模組節點標記 type=module
            mod_node = self.tree.insert(root, "end", text=mod['name'], open=True, values=("module",))

            # 嘗試讀取 spec 顯示函式
            proj_name = data.get('project_name', 'vibe_project').replace(" ", "_")
            spec_path = os.path.join(self.meta.workspace_root, proj_name, mod['name'], "spec.json")

            if os.path.exists(spec_path):
                # 如果有 Spec，將路徑存在 values[1]
                self.tree.item(mod_node, values=("module", spec_path))
                try:
                    with open(spec_path, 'r', encoding='utf-8') as f:
                        spec = json.load(f)
                        for func in spec.get('functions', []):
                            # 函式節點標記 type=function，並存入 spec_path
                            self.tree.insert(mod_node, "end", text=func['name'], values=("function", spec_path))
                except:
                    pass

    def on_select(self, event):
        """處理單擊選擇：顯示代碼或 JSON"""
        selected_items = self.tree.selection()
        if not selected_items: return

        # 只處理第一個被選中的項目進行顯示
        item = selected_items[0]
        values = self.tree.item(item, "values")
        text = self.tree.item(item, "text")

        if not values: return
        item_type = values[0]

        content_to_show = ""

        # 情境 A: 點擊函式 -> 顯示 .py 原始碼
        if item_type == "function":
            spec_path = values[1]
            mod_dir = os.path.dirname(spec_path)
            fname = "__init_logic__.py" if text == "__init__" else f"{text}.py"
            code_path = os.path.join(mod_dir, fname)
            if os.path.exists(code_path):
                with open(code_path, 'r', encoding='utf-8') as f:
                    content_to_show = f.read()
            else:
                content_to_show = "# Source code not found. Please implement first."

        # 情境 B: 點擊模組 -> 顯示 spec.json
        elif item_type == "module":
            # 檢查 values 是否有第二個元素 (spec_path)
            if len(values) > 1:
                spec_path = values[1]
                if os.path.exists(spec_path):
                    with open(spec_path, 'r', encoding='utf-8') as f:
                        # 格式化 JSON 以便閱讀
                        content_to_show = json.dumps(json.load(f), indent=4, ensure_ascii=False)
                else:
                    content_to_show = "// Spec not found. Run 'Refine Module' first."
            else:
                content_to_show = "// Spec not found. Run 'Refine Module' first."

        # 情境 C: 點擊專案根目錄 -> 顯示 architecture.json
        elif item_type == "project":
            if self.meta.current_architecture_path and os.path.exists(self.meta.current_architecture_path):
                with open(self.meta.current_architecture_path, 'r', encoding='utf-8') as f:
                    content_to_show = json.dumps(json.load(f), indent=4, ensure_ascii=False)

        # 更新中間的工作區
        if content_to_show:
            # 透過 mediator 呼叫 WorkSpace 的方法 (假設 WorkSpace 有 show_code)
            self.mediator.workspace.code_editor.delete("1.0", tk.END)
            self.mediator.workspace.code_editor.insert(tk.END, content_to_show)

    def show_context_menu(self, event):
        # 確保右鍵點擊也會觸發選取 (符合直覺)
        item = self.tree.identify_row(event.y)
        if item:
            # 如果該項目不在目前的選取範圍內，則單選它；如果在，則保持多選狀態
            if item not in self.tree.selection():
                self.tree.selection_set(item)
            self.menu.post(event.x_root, event.y_root)

    def show_arch_json(self):
        """強制顯示架構 JSON"""
        if self.meta.current_architecture_path:
            with open(self.meta.current_architecture_path, 'r') as f:
                content = json.dumps(json.load(f), indent=4)
                self.mediator.workspace.code_editor.delete("1.0", tk.END)
                self.mediator.workspace.code_editor.insert(tk.END, content)

    # --- 多選邏輯實作 ---

    def on_refine(self):
        """批次細化選中的模組"""
        items = self.tree.selection()
        # 過濾出類型為 'module' 的項目名稱
        target_modules = []
        for item in items:
            vals = self.tree.item(item, "values")
            if vals and vals[0] == "module":
                target_modules.append(self.tree.item(item, "text"))

        if not target_modules:
            self.mediator.log("[UI] No modules selected for refinement.")
            return

        def task():
            self.mediator.log(f"Batch Refining: {target_modules}")
            for mod in target_modules:
                # 檢查取消旗標
                if self.mediator._current_cancel_flag.is_set():
                    self.mediator.log("[UI] Batch Refine Cancelled.")
                    break

                self.mediator.log(f"Processing {mod}...")
                # 傳遞 cancel_event 給後端
                self.meta.refine_module(mod, cancel_event=self.mediator._current_cancel_flag)

            self.frame.after(0, self.refresh_tree)

        self.mediator.run_async(task)

    def on_implement(self):
        """批次實作選中的函式"""
        items = self.tree.selection()

        # 因為 generateFunctionCode 需要 spec_path，我們需要按模組分組
        # 結構: { spec_path: [func_name1, func_name2] }
        tasks = {}

        for item in items:
            vals = self.tree.item(item, "values")
            if vals and vals[0] == "function":
                fname = self.tree.item(item, "text")
                spec_path = vals[1]
                if spec_path not in tasks:
                    tasks[spec_path] = []
                tasks[spec_path].append(fname)

        if not tasks:
            self.mediator.log("[UI] No functions selected for implementation.")
            return

        def task():
            total_funcs = sum(len(fs) for fs in tasks.values())
            self.mediator.log(f"Batch Implementing {total_funcs} functions...")

            for spec_path, funcs in tasks.items():
                if self.mediator._current_cancel_flag.is_set(): break

                mod_name = os.path.basename(os.path.dirname(spec_path))
                self.mediator.log(f"Implementing in {mod_name}: {funcs}")

                # 傳遞 cancel_event
                self.meta.implement_functions(
                    spec_path,
                    funcs,
                    cancel_event=self.mediator._current_cancel_flag
                )

            self.mediator.log("Batch Implementation Finished.")
            # 重新整理顯示
            self.frame.after(0, lambda: self.on_select(None))

        self.mediator.run_async(task)
