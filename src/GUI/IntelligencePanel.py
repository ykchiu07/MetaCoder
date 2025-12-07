import tkinter as tk
from tkinter import ttk, scrolledtext

class IntelligencePanel:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        colors = getattr(mediator, 'colors', {'bg': '#333', 'fg': '#eee', 'console_bg': '#1e1f22'})

        self.frame = ttk.LabelFrame(parent, text="Vibe Intelligence")

        self.log_area = scrolledtext.ScrolledText(
            self.frame, height=20, bg=colors['console_bg'], fg="#00ff00",
            font=("Consolas", 9), insertbackground="white", selectbackground="#214283"
        )
        self.log_area.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(btn_frame, text="Run Diagnostics", command=self.on_diagnose).pack(fill=tk.X)

    def log(self, msg):
        self.log_area.insert(tk.END, f"> {msg}\n")
        self.log_area.see(tk.END)

    def on_diagnose(self):
        # [Fix] 使用新 API 獲取當前分頁的代碼
        code = self.mediator.workspace.get_active_code()

        # 這裡需要一個方法知道當前函式名，目前簡單起見，我們假設診斷的是「整個檔案」
        # 或者從 open_file 的 title 獲取
        func_name = "current_context"

        if not code:
            self.log("[Warn] Editor is empty or no file selected.")
            return

        def task():
            self.mediator.log(f"Running Diagnostics...")
            report = self.mediator.meta.run_dynamic_analysis(code, func_name)

            output = f"\n=== DIAGNOSTIC REPORT ===\n"
            output += f"Entropy (Logic): {report['entropies'][0]}\n"
            output += f"Entropy (Vision): {report['entropies'][1]}\n\n"
            output += "--- Logic Bottlenecks ---\n"
            output += report['logic_report'] + "\n"

            if report['vision_report']:
                output += "\n--- Visual Analysis ---\n"
                output += report['vision_report'] + "\n"

            self.mediator.log(output)

        self.mediator.run_async(task)
