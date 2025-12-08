import tkinter as tk
from tkinter import ttk
import os
import json
import datetime

class ProjectExplorer:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        self.meta = mediator.meta
        self._last_snapshot = {}
        self._is_refreshing = False

        # Loading 動畫相關
        self._loading_items = set() # 存放正在生成的 item ID
        self._spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self._spinner_idx = 0

        self.frame = ttk.LabelFrame(parent, text="Project Explorer")

        self.tree = ttk.Treeview(self.frame, selectmode="extended")
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<Button-1>", self._on_tree_click)

        self._init_menu()
        self.frame.after(1000, self._monitor_loop)

        # 啟動動畫迴圈
        self._animate_loading()


    def _animate_loading(self):
        """處理旋轉動畫"""
        if self._loading_items:
            char = self._spinner_chars[self._spinner_idx]
            self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner_chars)

            # 對於需要移除的 item (可能任務已結束但尚未刷新)，做個清理
            to_remove = []
            for item_id in self._loading_items:
                if not self.tree.exists(item_id):
                    to_remove.append(item_id)
                    continue

                # 更新文字，加上 spinner
                # 我們需要保留原始文字...這有點麻煩，簡單做法是 tag 識別
                current_text = self.tree.item(item_id, "text")
                # 如果已經有 spinner，替換掉
                # 假設 spinner 加在最後 "func_name  ⠋"
                clean_text = current_text.split("  ")[0]
                self.tree.item(item_id, text=f"{clean_text}  {char}")

            for i in to_remove:
                self._loading_items.discard(i)

        self.frame.after(100, self._animate_loading)

    def set_item_loading(self, name, is_loading):
        """
        [修正] 支援函式或模組名稱的 Loading。
        name: func_name 或 module_name
        """
        for item_id in self.tree.get_children(): # Project
            # 檢查是不是模組
            item_text = self.tree.item(item_id, "text").split(" ")[0]
            if item_text == name: # 這是根節點(Project)，通常不會 loading，略過
                pass

            for mod_id in self.tree.get_children(item_id): # Module
                mod_text = self.tree.item(mod_id, "text").split(" ")[0]
                if mod_text == name:
                    # 找到模組
                    if is_loading: self._loading_items.add(mod_id)
                    else: self._loading_items.discard(mod_id)
                    # 這裡不 return，因為可能還有同名的 func (雖然機率低)

                for func_id in self.tree.get_children(mod_id): # Function
                    func_text = self.tree.item(func_id, "text").split(" ")[0]
                    if func_text == name:
                        if is_loading: self._loading_items.add(func_id)
                        else: self._loading_items.discard(func_id)
                        return

    def _get_status_map(self, mod_dir):
        """讀取該模組的 .status.json"""
        status_path = os.path.join(mod_dir, ".status.json")
        if os.path.exists(status_path):
            try:
                with open(status_path, 'r') as f:
                    return json.load(f)
            except: pass
        return {}

    def _load_functions_to_tree(self, mod_node, mod_dir, spec_path):
        """[Refactor] 提取這個邏輯以支援 Main 和普通 Module"""
        status_map = self._get_status_map(mod_dir)
        try:
            with open(spec_path, 'r', encoding='utf-8') as f:
                spec = json.load(f)
            for func in spec.get('functions', []):
                fname = func['name']
                display_text = fname
                if status_map.get(fname, {}).get('status') == 'implemented':
                    display_text += " ✔"
                self.tree.insert(mod_node, "end", text=display_text, values=("function", spec_path))
        except Exception as e:
            print(f"[Explorer] Spec load error: {e}")

    def refresh_tree(self):
        if self._is_refreshing: return
        self._is_refreshing = True
        try:
            expanded_nodes = self._save_expanded_state()
            self._loading_items.clear()
            self.tree.delete(*self.tree.get_children())

            data = self.meta.get_project_tree()
            if not data: return

            proj_name = data.get('project_name', 'Project')
            root = self.tree.insert("", "end", text=proj_name, open=True, values=("project",))

            # 推斷專案根目錄
            if self.meta.current_architecture_path:
                project_base_dir = os.path.dirname(self.meta.current_architecture_path)
            else:
                project_base_dir = self.meta.workspace_root

            # --- [Fix 1] 顯示 Main Entry Point ---
            entry_point = data.get('entry_point')
            if entry_point:
                # 假設 entry_point 是一個檔案 (如 main.py)，我們將其視為一個特殊模組 "main"
                # 或者直接去讀 main/spec.json (這是 MetaCoder._create_main_entry_spec 的邏輯)
                main_mod_name = "main" # 根據 MetaCoder 的邏輯，它被放在 main 資料夾
                main_node = self.tree.insert(root, "end", text=main_mod_name, open=True, values=("module",))

                mod_dir = os.path.join(project_base_dir, main_mod_name)
                spec_path = os.path.join(mod_dir, "spec.json")
                if os.path.exists(spec_path):
                    self.tree.item(main_node, values=("module", spec_path))
                    self._load_functions_to_tree(main_node, mod_dir, spec_path)
            # ------------------------------------

            modules = data.get('modules', [])
            for mod in modules:
                mod_name = mod['name']
                mod_node = self.tree.insert(root, "end", text=mod_name, open=False, values=("module",))

                mod_dir = os.path.join(project_base_dir, mod_name)
                spec_path = os.path.join(mod_dir, "spec.json")

                if os.path.exists(spec_path):
                    self.tree.item(mod_node, values=("module", spec_path))
                    self._load_functions_to_tree(mod_node, mod_dir, spec_path)

            self._restore_expanded_state(expanded_nodes)
        finally:
            self._is_refreshing = False

    def _init_menu(self):
        self.menu = tk.Menu(self.frame, tearoff=0)
        self.menu.add_command(label="Refine Selected Modules (Phase 2)", command=self.on_refine)
        self.menu.add_command(label="Implement Selected Functions (Phase 3)", command=self.on_implement)
        self.menu.add_separator()
        self.menu.add_command(label="Show Architecture JSON", command=self.show_arch_json)

    def _on_tree_click(self, event):
        try: self.menu.unpost()
        except: pass

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if item not in self.tree.selection(): self.tree.selection_set(item)
            self.tree.focus_set()
            self.menu.post(event.x_root, event.y_root)

    def set_workspace(self, path):
        self._last_snapshot = {}
        self.tree.delete(*self.tree.get_children())
        self.frame.after_idle(self.refresh_tree)

    def _monitor_loop(self):
        if not self.frame.winfo_exists(): return
        try:
            if self.meta.workspace_root:
                snap = 0
                if self.meta.current_architecture_path and os.path.exists(self.meta.current_architecture_path):
                     snap = os.path.getmtime(self.meta.current_architecture_path)
                # 這裡可以加入對 .status.json 的監控，但為了效能，我們依賴操作觸發刷新
                if snap != self._last_snapshot.get('arch', 0):
                    self._last_snapshot['arch'] = snap
                    self.frame.after_idle(self.refresh_tree)
        except: pass
        self.frame.after(2000, self._monitor_loop)

    def _save_expanded_state(self):
        expanded = set()
        for child in self.tree.get_children():
            for grand_child in self.tree.get_children(child):
                if self.tree.item(grand_child, 'open'):
                    expanded.add(self.tree.item(grand_child, 'text'))
            if self.tree.item(child, 'open'):
                expanded.add("root_project")
        return expanded

    def _restore_expanded_state(self, expanded_set):
        for child in self.tree.get_children():
            if "root_project" in expanded_set:
                self.tree.item(child, open=True)
            for grand_child in self.tree.get_children(child):
                # 因為文字可能加上了 ✔，所以我們要比對原始名稱
                item_text = self.tree.item(grand_child, 'text').split(" ")[0]
                if item_text in expanded_set:
                    self.tree.item(grand_child, open=True)

    def on_select(self, event):
        selected_items = self.tree.selection()
        if not selected_items: return
        item = selected_items[0]
        values = self.tree.item(item, "values")
        text = self.tree.item(item, "text").split(" ")[0] # 去除勾勾或 spinner
        if not values: return
        item_type = values[0]
        file_path = None
        content_to_show = ""
        title = text
        if item_type == "function":
            spec_path = values[1]
            mod_dir = os.path.dirname(spec_path)
            fname = "__init_logic__.py" if text == "__init__" else f"{text}.py"
            file_path = os.path.join(mod_dir, fname)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f: content_to_show = f.read()
            else: content_to_show = "# Source code not found."
        elif item_type == "module":
            if len(values) > 1:
                spec_path = values[1]
                file_path = spec_path
                if os.path.exists(spec_path):
                    with open(spec_path, 'r', encoding='utf-8') as f: content_to_show = json.dumps(json.load(f), indent=4, ensure_ascii=False)
        elif item_type == "project":
            if self.meta.current_architecture_path:
                file_path = self.meta.current_architecture_path
                with open(file_path, 'r', encoding='utf-8') as f: content_to_show = json.dumps(json.load(f), indent=4, ensure_ascii=False)
        if content_to_show: self.mediator.workspace.open_file(title, content_to_show, file_path)

    def show_arch_json(self):
        if self.meta.current_architecture_path:
            with open(self.meta.current_architecture_path, 'r') as f:
                content = json.dumps(json.load(f), indent=4)
                self.mediator.workspace.open_file("architecture.json", content, self.meta.current_architecture_path)

    def on_refine(self):
        items = self.tree.selection()
        target_modules = []
        for item in items:
            vals = self.tree.item(item, "values")
            if vals and vals[0] == "module":
                mod_name = self.tree.item(item, "text").split(" ")[0] # 去掉可能存在的spinner或checkmark
                target_modules.append(mod_name)

        if not target_modules: return

        def task():
            for mod in target_modules:
                if self.mediator._current_cancel_flag.is_set(): break
                self.mediator.log(f"[Action] Refining module '{mod}'...")

                # --- [Fix 3] 在 UI 線程設置 loading ---
                self.frame.after(0, lambda m=mod: self.set_item_loading(m, True))

                res = self.mediator.meta.refine_module(mod, cancel_event=self.mediator._current_cancel_flag)

                if res is None:
                    self.mediator.log(f"[Fail] Refinement of {mod} failed/blocked.")

                # 完成後移除 loading (refresh_tree 會處理，但保險起見)
                self.frame.after(0, lambda m=mod: self.set_item_loading(m, False))

            self.frame.after(0, self.refresh_tree)

        self.mediator.run_async(task)

    def on_implement(self):
        items = self.tree.selection()
        tasks = {}

        for item in items:
            vals = self.tree.item(item, "values")
            if vals and vals[0] == "function":
                raw_text = self.tree.item(item, "text")
                fname = raw_text.split(" ")[0]
                spec_path = vals[1]
                parent_id = self.tree.parent(item)
                # 注意：這裡也要處理 spinner 的情況，取 split[0]
                mod_name = self.tree.item(parent_id, "text").split(" ")[0]

                key = (mod_name, spec_path)
                if key not in tasks: tasks[key] = []
                tasks[key].append(fname)

        if not tasks: return

        # 1. 檢查依賴 & 排程
        for (mod_name, spec_path), funcs in tasks.items():

            # [Fix 2] 強制依賴檢查並確保彈窗
            is_met = self.meta.check_dependencies_met(mod_name)
            print(f"[Debug] Dependency check for {mod_name}: {is_met}") # Debug Log

            if not is_met:
                msg = f"Cannot implement module '{mod_name}'.\nDependencies not met.\n\nPlease implement dependent modules first."
                self.mediator.log(f"[Blocked] {msg}")
                tk.messagebox.showwarning("Dependency Error", msg)
                continue # 跳過此模組

            # 2. 為每個函式建立獨立任務
            for func in funcs:
                self.set_item_loading(func, True)

                # (... Closure 設定保持不變 ...)
                def make_task(s_path, f_name, m_name):
                    def task_func():
                        self.mediator.log(f"[Action] Generating code for {f_name} (in {m_name})...")
                        result = self.meta.coder.implement_function_direct(
                            s_path, f_name,
                            self.meta.model_config['coder'],
                            cancel_event=self.mediator._current_cancel_flag
                        )
                        return result

                    def success_cb():
                        self.set_item_loading(f_name, False)
                        self.refresh_tree()

                        mod_dir = os.path.dirname(s_path)
                        code_path = os.path.join(mod_dir, "__init_logic__.py" if f_name == "__init__" else f"{f_name}.py")

                        # [Fix 4] 如果檔案存在，嘗試開啟或重載
                        if os.path.exists(code_path):
                            with open(code_path, 'r', encoding='utf-8') as f:
                                code = f.read()
                            # 這裡 open_file 如果已經開啟會切換 tab，我們需要確保內容更新
                            # 所以先呼叫 reload，再 open (switch)
                            self.mediator.workspace.reload_active_file()
                            self.mediator.workspace.open_file(f_name, code, code_path)
                    return task_func, success_cb

                t_func, s_cb = make_task(spec_path, func, mod_name)
                self.mediator.run_async(t_func, success_callback=s_cb)
