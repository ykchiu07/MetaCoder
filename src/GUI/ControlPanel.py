import tkinter as tk
from tkinter import ttk

class ControlPanel:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        # 使用 mediator 傳遞過來的暗色主題配置
        self.colors = getattr(mediator, 'colors', {'bg': '#333', 'fg': '#eee', 'editor_bg': '#1e1e1e'})

        self.frame = tk.Frame(parent, bg=self.colors['bg'])
        # 讓 frame 根據內容自動調整高度，不強制 height=100，避免按鈕被切掉
        self.frame.pack(fill=tk.X)

        # --- 1. 輸入區 ---
        tk.Label(self.frame, text="Requirement Prompt:", bg=self.colors['bg'], fg=self.colors['fg']).pack(anchor="w", padx=5)

        # 輸入框 (手動設定顏色以符合暗色主題)
        self.entry = tk.Text(self.frame, height=3, bg=self.colors['editor_bg'], fg="white", insertbackground="white", relief=tk.FLAT)
        self.entry.pack(fill=tk.X, padx=5, pady=2)

        # --- 2. 控制按鈕與狀態區 ---
        ctrl_frame = tk.Frame(self.frame, bg=self.colors['bg'])
        ctrl_frame.pack(fill=tk.X, pady=5)

        self.status_lbl = tk.Label(ctrl_frame, text="Ready", fg="#4a88c7", bg=self.colors['bg'])
        self.status_lbl.pack(side=tk.LEFT, padx=5)

        # 這是那個會變身的按鈕 (Generate / Stop)
        self.action_btn = ttk.Button(ctrl_frame, text="GENERATE ARCHITECTURE", command=self.on_click)
        self.action_btn.pack(side=tk.RIGHT, padx=5)

        self.is_running = False

        # --- 3. [新增] 視圖模式切換區 ---
        self.current_mode = tk.StringVar(value="creation") # 預設模式
        self._init_mode_switcher()

    def _init_mode_switcher(self):
        """初始化視圖切換按鈕列"""
        mode_frame = tk.Frame(self.frame, bg=self.colors['bg'])
        mode_frame.pack(fill=tk.X, pady=(0, 5), padx=5)

        # 定義五種模式
        modes = [
            ("Creation", "creation"),
            ("Gen. Test", "general_test"),
            ("Static Eval", "static_eval"),
            ("Runtime", "runtime_analysis"),
            ("Chaos", "chaos_test")
        ]

        # 按鈕樣式設定 (模擬暗色系 Toggle Button)
        btn_bg = "#444"
        select_color = "#666" # 選中時的顏色

        for text, mode_val in modes:
            btn = tk.Radiobutton(
                mode_frame,
                text=text,
                value=mode_val,
                variable=self.current_mode,
                indicatoron=0,           # 去除圓點，變成按鈕外觀
                bg=btn_bg,
                fg=self.colors['fg'],
                selectcolor=select_color,
                activebackground=select_color,
                activeforeground="white",
                bd=0,                    # 無邊框風格
                command=self.on_mode_switch
            )
            # 使用 pack side=LEFT 並設定 expand/fill 讓按鈕平均分佈
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

    def on_mode_switch(self):
        """處理模式切換"""
        mode = self.current_mode.get()
        # 暫時只透過 Mediator 記錄 Log，不必實作具體邏輯
        if hasattr(self.mediator, 'log'):
            self.mediator.log(f"Switched View Mode to: {mode}")

        # 未來這裡可以呼叫: self.mediator.switch_workspace_view(mode)

    # --- 原有邏輯保持不變 ---

    def set_status(self, msg):
        self.status_lbl.config(text=msg)

    def set_running_state(self, running: bool):
        """由 MainWindow 呼叫，切換按鈕型態"""
        self.is_running = running
        if running:
            self.action_btn.config(text="STOP GENERATION")
            self.status_lbl.config(fg="#ff5555") # 執行中變紅色或其他醒目顏色
        else:
            self.action_btn.config(text="GENERATE ARCHITECTURE")
            self.status_lbl.config(fg="#4a88c7")

    def on_click(self):
        if self.is_running:
            # 如果正在跑，按下就是停止
            self.mediator.stop_current_task()
        else:
            # 如果沒在跑，按下就是開始
            self.on_generate()

    def on_generate(self):
        req = self.entry.get("1.0", tk.END).strip()
        if not req: return

        def task():
            self.mediator.log("Generating Architecture...")
            # 檢查取消旗標
            if self.mediator._current_cancel_flag.is_set(): return

            res = self.mediator.meta.init_project(req)
            self.mediator.log(f"Saved: {res.structure_file_path}")

        def on_success():
            # 確保 ProjectExplorer 存在且能刷新
            if hasattr(self.mediator, 'nav'):
                self.mediator.nav.refresh_tree()

        # 呼叫 MainWindow 的執行器
        self.mediator.run_async(task, success_callback=on_success)
