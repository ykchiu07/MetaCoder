import tkinter as tk
from tkinter import ttk, messagebox

class ControlPanel:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        self.colors = getattr(mediator, 'colors', {'bg': '#333', 'fg': '#eee', 'editor_bg': '#1e1e1e'})

        self.frame = tk.Frame(parent, bg=self.colors['bg'])
        self.frame.pack(fill=tk.X)

        # Requirement Input
        tk.Label(self.frame, text="Context / Prompt:", bg=self.colors['bg'], fg=self.colors['fg']).pack(anchor="w", padx=5)
        self.entry = tk.Text(self.frame, height=3, bg=self.colors['editor_bg'], fg="white", insertbackground="white", relief=tk.FLAT)
        self.entry.pack(fill=tk.X, padx=5, pady=2)

        # Control Area
        ctrl_frame = tk.Frame(self.frame, bg=self.colors['bg'])
        ctrl_frame.pack(fill=tk.X, pady=5)

        self.status_lbl = tk.Label(ctrl_frame, text="Ready", fg="#4a88c7", bg=self.colors['bg'])
        self.status_lbl.pack(side=tk.LEFT, padx=5)

        # 主操作按鈕
        self.action_btn = ttk.Button(ctrl_frame, text="EXECUTE", command=self.on_click)
        self.action_btn.pack(side=tk.RIGHT, padx=5)

        self.is_running = False

        # 模式選擇器
        self.current_mode = tk.StringVar(value="creation")
        self._init_mode_switcher()

        # 初始化按鈕文字
        self.update_button_state()

    def _init_mode_switcher(self):
        mode_frame = tk.Frame(self.frame, bg=self.colors['bg'])
        mode_frame.pack(fill=tk.X, pady=(0, 5), padx=5)

        # 定義模式與標籤
        modes = [
            ("Creation", "creation"),
            ("Gen. Test", "general_test"),
            ("Static Eval", "static_eval"),
            ("Runtime", "runtime_analysis"),
            ("Chaos", "chaos_test")
        ]

        btn_bg, select_color = "#444", "#666"
        for text, mode_val in modes:
            tk.Radiobutton(
                mode_frame, text=text, value=mode_val, variable=self.current_mode,
                indicatoron=0, bg=btn_bg, fg=self.colors['fg'],
                selectcolor=select_color, activebackground=select_color,
                activeforeground="white", bd=0,
                command=self.on_mode_switch
            ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

    def on_mode_switch(self):
        """切換模式時更新按鈕文字與 Dependency Graph"""
        mode = self.current_mode.get()
        if hasattr(self.mediator, 'log'):
            self.mediator.log(f"Switched Mode to: {mode}")

        self.update_button_state()

        # 通知 Workspace 重繪 Graph (變色)
        if hasattr(self.mediator, 'workspace'):
            self.mediator.workspace.draw_dependency_graph()

    def update_button_state(self):
        """根據當前模式改變按鈕文字"""
        if self.is_running:
            self.action_btn.config(text="STOP PROCESS")
            return

        mode = self.current_mode.get()
        text = "ACTION"
        if mode == "creation":
            text = "GENERATE ARCHITECTURE" # 預設，若有點選 Project Explorer 會被覆蓋
        elif mode == "general_test":
            text = "GENERATE & RUN TESTS"
        elif mode == "static_eval":
            text = "RUN STATIC ANALYSIS"
        elif mode == "runtime_analysis":
            text = "RUN RUNTIME PROFILE"
        elif mode == "chaos_test":
            text = "LAUNCH CHAOS CAMPAIGN"

        self.action_btn.config(text=text)

    # [API] 供外部 (ProjectExplorer) 更新上下文
    def update_context_button(self, action_type: str, target=None):
        self.current_target = target
        if not self.is_running and self.current_mode.get() == "creation":
            if action_type == 'impl':
                self.action_btn.config(text=f"IMPLEMENT: {target[0]}")
            elif action_type == 'refine':
                self.action_btn.config(text=f"REFINE: {target}")

    def set_status(self, msg):
        self.status_lbl.config(text=msg)

    def set_running_state(self, running: bool):
        self.is_running = running
        if running:
            self.action_btn.config(text="STOP PROCESS")
            self.status_lbl.config(fg="#ff5555")
        else:
            self.update_button_state()
            self.status_lbl.config(fg="#4a88c7")

    def on_click(self):
        if self.is_running:
            self.mediator.stop_current_task()
            return

        mode = self.current_mode.get()
        target_items = self.mediator.nav.tree.selection()

        # 獲取選取項目的名稱 (module 或 function)
        selected_name = None
        selected_type = None
        spec_path = None

        if target_items:
            item = target_items[0]
            vals = self.mediator.nav.tree.item(item, "values")
            raw_text = self.mediator.nav.tree.item(item, "text").split(" ")[0]
            selected_name = raw_text
            if vals:
                selected_type = vals[0]
                if len(vals) > 1: spec_path = vals[1]

        # --- 分派邏輯 ---

        if mode == "creation":
            # 維持原本的創建邏輯
            req = self.entry.get("1.0", tk.END).strip()
            # 如果按鈕顯示的是 Implement/Refine，則執行對應動作
            btn_text = self.action_btn.cget("text")

            if "IMPLEMENT" in btn_text and selected_type == 'function':
                self.mediator.controls.on_generate_impl(spec_path, selected_name)
            elif "REFINE" in btn_text and selected_type == 'module':
                self.mediator.controls.on_generate_refine(selected_name)
            else:
                self.on_generate_arch()

        elif mode == "general_test":
            if not selected_name:
                messagebox.showwarning("Select Target", "Please select a Module or Function to test.")
                return
            self.mediator.meta.execute_test_workflow(selected_name, selected_type, spec_path, self.mediator)

        elif mode == "static_eval":
            self.mediator.log("[Static] Refreshing scores...")
            self.mediator.workspace.draw_dependency_graph() # 其實就是刷新圖表

        elif mode == "runtime_analysis":
            if selected_type != 'function':
                messagebox.showwarning("Target Error", "Runtime analysis requires selecting a Function.")
                return
            # 獲取程式碼
            code = self.mediator.workspace.get_active_code()
            if not code:
                messagebox.showwarning("Code Error", "Please open the function code in the editor first.")
                return
            self.mediator.meta.execute_runtime_workflow(selected_name, code, self.mediator)

        elif mode == "chaos_test":
            if selected_type != 'module':
                messagebox.showwarning("Target Error", "Chaos tests target a specific Module.")
                return
            self.mediator.meta.execute_chaos_workflow(selected_name, self.mediator)

    # 保留原本的 creation helpers
    def on_generate_arch(self):
        req = self.entry.get("1.0", tk.END).strip()
        if not req: return
        def task():
            self.mediator.log("Generating Architecture...")
            res = self.mediator.meta.init_project(req)
            self.mediator.log(f"Saved: {res.structure_file_path}")
        def on_success():
            if hasattr(self.mediator, 'nav'): self.mediator.nav.refresh_tree()
        self.mediator.run_async(task, success_callback=on_success)

    def on_generate_impl(self, spec_path, func_name):
        self.mediator.nav.set_item_loading(func_name, True)
        def task():
            self.mediator.log(f"[Start] Implementing {func_name}...")
            self.mediator.meta.implement_functions(spec_path, [func_name], cancel_event=self.mediator._current_cancel_flag)
            self.mediator.nav.frame.after(0, self.mediator.nav.refresh_tree)
        self.mediator.run_async(task)

    def on_generate_refine(self, mod_name):
        def task():
            self.mediator.log(f"[Start] Refining {mod_name}...")
            self.mediator.meta.refine_module(mod_name, cancel_event=self.mediator._current_cancel_flag)
            self.mediator.nav.frame.after(0, self.mediator.nav.refresh_tree)
        self.mediator.run_async(task)
