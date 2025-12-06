import tkinter as tk
from tkinter import ttk, scrolledtext

class WorkSpace:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        self.frame = ttk.Frame(parent)

        self.notebook = ttk.Notebook(self.frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1
        self.code_editor = scrolledtext.ScrolledText(self.notebook, font=("Consolas", 11))
        self.notebook.add(self.code_editor, text="Code Editor")

        # Tab 2
        self.canvas = tk.Canvas(self.notebook, bg="white")
        self.notebook.add(self.canvas, text="Dependency Graph")

    def show_code(self, content):
        self.code_editor.delete("1.0", tk.END)
        self.code_editor.insert(tk.END, content)
