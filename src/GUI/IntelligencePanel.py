import tkinter as tk
from tkinter import ttk, scrolledtext

class IntelligencePanel:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        self.frame = ttk.LabelFrame(parent, text="Vibe Intelligence")

        self.log_area = scrolledtext.ScrolledText(self.frame, height=20, bg="#f0f0f0", font=("Arial", 9))
        self.log_area.pack(fill=tk.BOTH, expand=True)

        btn = ttk.Button(self.frame, text="Run Diagnostics", command=self.on_diagnose)
        btn.pack(fill=tk.X, pady=5)

    def log(self, msg):
        self.log_area.insert(tk.END, f"> {msg}\n")
        self.log_area.see(tk.END)

    def on_diagnose(self):
        # 呼叫 mediator 轉發請求
        pass
