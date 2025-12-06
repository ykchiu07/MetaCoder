import tkinter as tk
from tkinter import ttk

class ControlPanel:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        self.frame = ttk.Frame(parent, height=100)

        ttk.Label(self.frame, text="Requirement Prompt:").pack(anchor="w")
        self.entry = tk.Text(self.frame, height=3)
        self.entry.pack(fill=tk.X, padx=5)

        ctrl_frame = ttk.Frame(self.frame)
        ctrl_frame.pack(fill=tk.X, pady=5)

        self.status_lbl = ttk.Label(ctrl_frame, text="Ready", foreground="blue")
        self.status_lbl.pack(side=tk.LEFT, padx=5)

        ttk.Button(ctrl_frame, text="GENERATE ARCHITECTURE", command=self.on_generate).pack(side=tk.RIGHT, padx=5)

    def set_status(self, msg):
        self.status_lbl.config(text=msg)

    def on_generate(self):
        req = self.entry.get("1.0", tk.END).strip()
        if not req: return

        def task():
            self.mediator.log("Generating Architecture...")
            res = self.mediator.meta.init_project(req)
            self.mediator.log(f"Saved: {res.structure_file_path}")
            # 通知導航欄刷新
            self.frame.after(0, self.mediator.nav.refresh_tree)

        self.mediator.run_async(task)
