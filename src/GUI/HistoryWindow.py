import tkinter as tk
from tkinter import ttk, messagebox

class HistoryWindow:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        self.window = tk.Toplevel(parent)
        self.window.title("Project History & Version Control")
        self.window.geometry("600x400")
        self.window.configure(bg="#2b2b2b")

        # 列表區
        columns = ("short_hash", "date", "message")
        self.tree = ttk.Treeview(self.window, columns=columns, show="headings")
        self.tree.heading("short_hash", text="Hash")
        self.tree.heading("date", text="Date")
        self.tree.heading("message", text="Message")

        self.tree.column("short_hash", width=80)
        self.tree.column("date", width=150)
        self.tree.column("message", width=350)

        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 按鈕區
        btn_frame = tk.Frame(self.window, bg="#2b2b2b")
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(btn_frame, text="Rollback to Selected", command=self.on_rollback,
                  bg="#ff5555", fg="white").pack(side=tk.RIGHT)

        tk.Button(btn_frame, text="Refresh", command=self.refresh,
                  bg="#4a88c7", fg="white").pack(side=tk.LEFT)

        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        history = self.mediator.meta.vc.getHistory(limit=20)
        for h in history:
            self.tree.insert("", "end", values=(h['short_hash'], h['date'], h['message']))

    def on_rollback(self):
        selected = self.tree.selection()
        if not selected: return

        item = self.tree.item(selected[0])
        commit_hash = item['values'][0]
        msg = item['values'][2]

        if messagebox.askyesno("Confirm Rollback", f"Are you sure you want to rollback to:\n[{commit_hash}] {msg}\n\nThis will reset ALL files."):
            success = self.mediator.meta.vc.rollbackVersion(commit_hash)
            if success:
                messagebox.showinfo("Success", "Project rolled back.")
                # 通知主視窗刷新
                self.mediator.nav.refresh_tree()
                self.mediator.workspace.clear_all_editors()
                self.window.destroy()
            else:
                messagebox.showerror("Error", "Rollback failed.")
