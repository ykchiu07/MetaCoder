import tkinter as tk
from tkinter import ttk

class ControlPanel:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        # 使用 mediator 傳遞過來的暗色主題配置
        colors = getattr(mediator, 'colors', {'bg': '#333', 'fg': '#eee'})

        self.frame = tk.Frame(parent, height=100, bg=colors['bg'])

        # 輸入區標題
        tk.Label(self.frame, text="Requirement Prompt:", bg=colors['bg'], fg=colors['fg']).pack(anchor="w", padx=5)

        # 輸入框 (手動設定顏色以符合暗色主題)
        self.entry = tk.Text(self.frame, height=3, bg=colors['editor_bg'], fg="white", insertbackground="white", relief=tk.FLAT)
        self.entry.pack(fill=tk.X, padx=5, pady=2)

        # 控制按鈕區
        ctrl_frame = tk.Frame(self.frame, bg=colors['bg'])
        ctrl_frame.pack(fill=tk.X, pady=5)

        self.status_lbl = tk.Label(ctrl_frame, text="Ready", fg="#4a88c7", bg=colors['bg'])
        self.status_lbl.pack(side=tk.LEFT, padx=5)

        # 這是那個會變身的按鈕
        self.action_btn = ttk.Button(ctrl_frame, text="GENERATE ARCHITECTURE", command=self.on_click)
        self.action_btn.pack(side=tk.RIGHT, padx=5)

        self.is_running = False

    def set_status(self, msg):
        self.status_lbl.config(text=msg)

    def set_running_state(self, running: bool):
        """由 MainWindow 呼叫，切換按鈕型態"""
        self.is_running = running
        if running:
            self.action_btn.config(text="STOP GENERATION")
        else:
            self.action_btn.config(text="GENERATE ARCHITECTURE")

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
            # 檢查取消旗標的範例 (雖然 generateHighStructure 內部目前沒檢查)
            if self.mediator._current_cancel_flag.is_set(): return

            res = self.mediator.meta.init_project(req)
            self.mediator.log(f"Saved: {res.structure_file_path}")

        def on_success():
            self.mediator.nav.refresh_tree()

        # 呼叫 MainWindow 的執行器
        self.mediator.run_async(task, success_callback=on_success)
