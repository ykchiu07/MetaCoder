import tkinter as tk
from tkinter import ttk

class ControlPanel:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        self.colors = getattr(mediator, 'colors', {'bg': '#333', 'fg': '#eee', 'editor_bg': '#1e1e1e'})

        self.frame = tk.Frame(parent, bg=self.colors['bg'])
        self.frame.pack(fill=tk.X)

        # Requirement Input
        tk.Label(self.frame, text="Requirement Prompt:", bg=self.colors['bg'], fg=self.colors['fg']).pack(anchor="w", padx=5)
        self.entry = tk.Text(self.frame, height=3, bg=self.colors['editor_bg'], fg="white", insertbackground="white", relief=tk.FLAT)
        self.entry.pack(fill=tk.X, padx=5, pady=2)

        # Control Area
        ctrl_frame = tk.Frame(self.frame, bg=self.colors['bg'])
        ctrl_frame.pack(fill=tk.X, pady=5)

        self.status_lbl = tk.Label(ctrl_frame, text="Ready", fg="#4a88c7", bg=self.colors['bg'])
        self.status_lbl.pack(side=tk.LEFT, padx=5)

        # [Fix 4] 動態按鈕：預設是 Architecture
        self.action_btn = ttk.Button(ctrl_frame, text="GENERATE ARCHITECTURE", command=self.on_click)
        self.action_btn.pack(side=tk.RIGHT, padx=5)

        # 儲存當前按鈕的模式 ('arch', 'impl', 'refine')
        self.current_action_mode = 'arch'
        self.current_target = None # 儲存目標 (spec path, func name 等)

        self.is_running = False
        self.current_mode = tk.StringVar(value="creation")
        self._init_mode_switcher()

    def _init_mode_switcher(self):
        # (保持不變)
        mode_frame = tk.Frame(self.frame, bg=self.colors['bg'])
        mode_frame.pack(fill=tk.X, pady=(0, 5), padx=5)
        modes = [("Creation", "creation"), ("Gen. Test", "general_test"), ("Static Eval", "static_eval"), ("Runtime", "runtime_analysis"), ("Chaos", "chaos_test")]
        btn_bg, select_color = "#444", "#666"
        for text, mode_val in modes:
            tk.Radiobutton(mode_frame, text=text, value=mode_val, variable=self.current_mode, indicatoron=0, bg=btn_bg, fg=self.colors['fg'], selectcolor=select_color, activebackground=select_color, activeforeground="white", bd=0, command=self.on_mode_switch).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

    def on_mode_switch(self):
        if hasattr(self.mediator, 'log'):
            self.mediator.log(f"Switched View Mode to: {self.current_mode.get()}")

    def set_status(self, msg):
        self.status_lbl.config(text=msg)

    def set_running_state(self, running: bool):
        self.is_running = running
        if running:
            self.action_btn.config(text="STOP GENERATION")
            self.status_lbl.config(fg="#ff5555")
        else:
            # 恢復原本的按鈕文字
            self._restore_button_text()
            self.status_lbl.config(fg="#4a88c7")

    def _restore_button_text(self):
        if self.current_action_mode == 'arch':
            self.action_btn.config(text="GENERATE ARCHITECTURE")
        elif self.current_action_mode == 'impl':
            self.action_btn.config(text=f"IMPLEMENT FUNCTION: {self.current_target[0]}")
        elif self.current_action_mode == 'refine':
            self.action_btn.config(text=f"REFINE MODULE: {self.current_target}")

    # [Fix 4] 對外 API：更新按鈕上下文
    def update_context_button(self, mode: str, target=None):
        """
        mode: 'arch', 'impl', 'refine'
        target: 相關資料 (如函式名)
        """
        self.current_action_mode = mode
        self.current_target = target
        if not self.is_running:
            self._restore_button_text()

    def on_click(self):
        if self.is_running:
            self.mediator.stop_current_task()
        else:
            # 根據當前模式分派任務
            if self.current_action_mode == 'arch':
                self.on_generate_arch()
            elif self.current_action_mode == 'impl':
                # target: (func_name, spec_path)
                func, spec = self.current_target
                # 呼叫 ProjectExplorer 的 implement 邏輯 (透過 mediator)
                # 這裡直接呼叫 meta 比較快
                self.on_generate_impl(spec, func)
            elif self.current_action_mode == 'refine':
                mod = self.current_target
                self.on_generate_refine(mod)

    def on_generate_arch(self):
        req = self.entry.get("1.0", tk.END).strip()
        if not req: return
        def task():
            self.mediator.log("Generating Architecture...")
            if self.mediator._current_cancel_flag.is_set(): return
            res = self.mediator.meta.init_project(req)
            self.mediator.log(f"Saved: {res.structure_file_path}")
        def on_success():
            if hasattr(self.mediator, 'nav'): self.mediator.nav.refresh_tree()
        self.mediator.run_async(task, success_callback=on_success)

    def on_generate_impl(self, spec_path, func_name):
        # 借用 ProjectExplorer 的 loading 邏輯比較麻煩，這裡直接觸發 meta
        # 但為了保持 UI 一致性，最好還是走 ProjectExplorer 的邏輯
        # 簡單做法：發送請求給 Nav
        if hasattr(self.mediator, 'nav'):
            # 模擬選取並執行
            # 但這裡我們直接調用 meta，並手動設置 loading
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
