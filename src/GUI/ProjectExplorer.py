import tkinter as tk
from tkinter import ttk
import os
import json
import datetime

class ProjectExplorer:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        self.meta = mediator.meta

        # 監控狀態
        self._last_snapshot = {}
        self._monitor_active = True
        self._is_refreshing = False

        self.frame = ttk.LabelFrame(parent, text="Project Explorer (Debug Mode)")

        # 啟用多選模式
        self.tree = ttk.Treeview(self.frame, selectmode="extended")
        self.tree.pack(fill=tk.BOTH, expand=True)

        # 綁定事件
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Button-3>", self.show_context_menu)

        self._init_menu()

        print(f"[DEBUG {self._now()}] Init complete. Starting monitor loop in 1s...")
        # 啟動自動監控
        self.frame.after(1000, self._monitor_loop)
        # [新增] 綁定全域點擊事件以關閉選單
        # 當使用者點擊 Treeview 任何地方時，嘗試關閉選單
        self.tree.bind("<Button-1>", self._on_tree_click)

    def _now(self):
        """取得當前時間字串，方便除錯"""
        return datetime.datetime.now().strftime("%H:%M:%S")

    def _init_menu(self):
        self.menu = tk.Menu(self.frame, tearoff=0)
        self.menu.add_command(label="Refine Selected Modules (Phase 2)", command=self.on_refine)
        self.menu.add_command(label="Implement Selected Functions (Phase 3)", command=self.on_implement)
        self.menu.add_separator()
        self.menu.add_command(label="Show Architecture JSON", command=self.show_arch_json)

    def _get_snapshot(self):
        """建立檔案系統指紋"""
        snapshot = {}
        root_path = self.meta.workspace_root

        # DEBUG: 檢查路徑是否有效
        if not root_path:
            # print(f"[DEBUG {self._now()}] Snapshot: workspace_root is None or Empty.") # 太吵，先註解
            return snapshot

        if not os.path.exists(root_path):
            print(f"[DEBUG {self._now()}] Snapshot: Path does not exist on disk: {root_path}")
            return snapshot

        # 監控 Architecture JSON
        if self.meta.current_architecture_path and os.path.exists(self.meta.current_architecture_path):
            try:
                snapshot['arch.json'] = os.path.getmtime(self.meta.current_architecture_path)
            except OSError:
                pass

        # 監控專案資料夾
        try:
            file_count = 0
            for root, dirs, files in os.walk(root_path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != "__pycache__"]
                for file in files:
                    if file.endswith('.py') or file.endswith('.json'):
                        full_path = os.path.join(root, file)
                        try:
                            rel_path = os.path.relpath(full_path, root_path)
                            snapshot[rel_path] = os.path.getmtime(full_path)
                            file_count += 1
                        except OSError:
                            pass
            # print(f"[DEBUG {self._now()}] Snapshot scan finished. Files tracked: {file_count}")
        except Exception as e:
            print(f"[DEBUG {self._now()}] Snapshot Error: {e}")

        return snapshot

    def set_workspace(self, path):
        self._last_snapshot = {}
        # 強制清空樹狀圖，給使用者「正在重新載入」的視覺回饋
        self.tree.delete(*self.tree.get_children())
        self.frame.after_idle(self.refresh_tree)

    def _monitor_loop(self):
        """除錯版監控迴圈 (已修正初次載入不顯示的問題)"""
        if not self.frame.winfo_exists():
            return

        interval = 2000

        try:
            if not self.meta.workspace_root:
                # 暫時沒 Workspace，安靜等待
                pass
            else:
                current_snapshot = self._get_snapshot()

                # 分支 4: 狀態比對
                if not self._last_snapshot:
                    print(f"[DEBUG {self._now()}] Monitor Loop: First run / Workspace Changed. Found {len(current_snapshot)} files.")
                    self._last_snapshot = current_snapshot

                    # === [修正點] ===
                    # 第一次抓到檔案時，必須立刻刷新畫面！
                    self.frame.after_idle(self.refresh_tree)

                elif current_snapshot != self._last_snapshot:
                    print(f"[DEBUG {self._now()}] Monitor Loop: !!! CHANGE DETECTED !!!")
                    self._last_snapshot = current_snapshot
                    self.frame.after_idle(self.refresh_tree)

        except Exception as e:
            print(f"[DEBUG {self._now()}] !!! Monitor Loop CRASHED !!! Error: {e}")
            interval = 5000

        self.frame.after(interval, self._monitor_loop)

    # --- 狀態保留與刷新邏輯 ---

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
                if self.tree.item(grand_child, 'text') in expanded_set:
                    self.tree.item(grand_child, open=True)

    def refresh_tree(self):
        print(f"[DEBUG {self._now()}] Action: Refreshing TreeView...")
        if self._is_refreshing:
            print(f"[DEBUG {self._now()}] Skipped refresh (already in progress).")
            return
        self._is_refreshing = True

        try:
            expanded_nodes = self._save_expanded_state()
            self.tree.delete(*self.tree.get_children())

            data = self.meta.get_project_tree()
            if not data:
                print(f"[DEBUG {self._now()}] Refresh: No project data found from meta.")
                return

            root = self.tree.insert("", "end", text=data.get('project_name', 'Project'), open=True, values=("project",))

            # 顯示模組與函式
            modules = data.get('modules', [])
            print(f"[DEBUG {self._now()}] Refresh: Rendering {len(modules)} modules.")

            for mod in modules:
                mod_node = self.tree.insert(root, "end", text=mod['name'], open=False, values=("module",))

                proj_name = data.get('project_name', 'vibe_project').replace(" ", "_")
                spec_path = os.path.join(self.meta.workspace_root, proj_name, mod['name'], "spec.json")

                if os.path.exists(spec_path):
                    self.tree.item(mod_node, values=("module", spec_path))
                    try:
                        with open(spec_path, 'r', encoding='utf-8') as f:
                            spec = json.load(f)
                            for func in spec.get('functions', []):
                                self.tree.insert(mod_node, "end", text=func['name'], values=("function", spec_path))
                    except Exception as e:
                        print(f"[DEBUG] Error reading spec {spec_path}: {e}")

            self._restore_expanded_state(expanded_nodes)
            print(f"[DEBUG {self._now()}] Refresh Complete.")

        except Exception as e:
            print(f"[DEBUG {self._now()}] Refresh Tree Error: {e}")
        finally:
            self._is_refreshing = False

    def _on_tree_click(self, event):
        """點擊樹狀圖時，確保選單消失"""
        # unpost 在某些系統上可能無效，標準做法是利用 focus 轉移或再次點擊
        # 但在 Tkinter 中，menu.unpost() 通常能解決懸浮問題
        try:
            self.menu.unpost()
        except:
            pass

    # --- 下方邏輯保持不變 ---
    def on_select(self, event):
        selected_items = self.tree.selection()
        if not selected_items: return

        item = selected_items[0]
        values = self.tree.item(item, "values")
        text = self.tree.item(item, "text")

        if not values: return
        item_type = values[0]
        content_to_show = ""

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

        elif item_type == "module":
            if len(values) > 1:
                spec_path = values[1]
                if os.path.exists(spec_path):
                    with open(spec_path, 'r', encoding='utf-8') as f:
                        content_to_show = json.dumps(json.load(f), indent=4, ensure_ascii=False)
                else:
                    content_to_show = "// Spec not found. Run 'Refine Module' first."
            else:
                content_to_show = "// Spec not found. Run 'Refine Module' first."

        elif item_type == "project":
            if self.meta.current_architecture_path and os.path.exists(self.meta.current_architecture_path):
                with open(self.meta.current_architecture_path, 'r', encoding='utf-8') as f:
                    content_to_show = json.dumps(json.load(f), indent=4, ensure_ascii=False)

        if content_to_show:
            self.mediator.workspace.code_editor.delete("1.0", tk.END)
            self.mediator.workspace.code_editor.insert(tk.END, content_to_show)

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            if item not in self.tree.selection():
                self.tree.selection_set(item)
            # post 之前先確保 tree 獲得焦點
            self.tree.focus_set()
            self.menu.post(event.x_root, event.y_root)

    def show_arch_json(self):
        if self.meta.current_architecture_path:
            with open(self.meta.current_architecture_path, 'r') as f:
                content = json.dumps(json.load(f), indent=4)
                self.mediator.workspace.code_editor.delete("1.0", tk.END)
                self.mediator.workspace.code_editor.insert(tk.END, content)

    def on_refine(self):
        items = self.tree.selection()
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
                if self.mediator._current_cancel_flag.is_set():
                    break
                self.mediator.log(f"Processing {mod}...")
                self.meta.refine_module(mod, cancel_event=self.mediator._current_cancel_flag)

            self.frame.after(0, self.refresh_tree)

        self.mediator.run_async(task)

    def on_implement(self):
        items = self.tree.selection()
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
                self.meta.implement_functions(
                    spec_path, funcs, cancel_event=self.mediator._current_cancel_flag
                )

            self.mediator.log("Batch Implementation Finished.")
            self.frame.after(0, self.refresh_tree)

        self.mediator.run_async(task)
