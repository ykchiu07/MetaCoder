import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from tkinter import messagebox

class VibeCoderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Vibe-Coder IDE (Local LLM Edition)")
        self.root.geometry("1400x900")

        # 設定樣式
        self.style = ttk.Style()
        self.style.theme_use('clam') # 使用較現代的風格

        # 1. 頂部選單與工具列
        self._init_menu()
        self._init_top_bar()

        # 2. 主視窗分割 (垂直分割：上方主要工作區 / 下方輸入與終端區)
        self.main_vertical_pane = tk.PanedWindow(self.root, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        self.main_vertical_pane.pack(fill=tk.BOTH, expand=True)

        # 3. 上方區域分割 (水平分割：左側導航 / 中間工作區 / 右側智囊面板)
        self.upper_horizontal_pane = tk.PanedWindow(self.main_vertical_pane, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.main_vertical_pane.add(self.upper_horizontal_pane, height=600)

        # --- 左側：專案導航 (Project Nav) ---
        self._init_left_panel()

        # --- 中間：工作區 (Workspace) ---
        self._init_center_panel()

        # --- 右側：智囊面板 (AI & Metrics) ---
        self._init_right_panel()

        # 4. 下方區域分割 (水平分割：左側需求輸入 / 右側終端機)
        self.bottom_horizontal_pane = tk.PanedWindow(self.main_vertical_pane, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        self.main_vertical_pane.add(self.bottom_horizontal_pane)

        # --- 下方左側：需求輸入 ---
        self._init_bottom_input_panel()

        # --- 下方右側：終端機 ---
        self._init_bottom_terminal_panel()

        # 狀態列
        self._init_status_bar()

    def _init_menu(self):
        menubar = tk.Menu(self.root)

        # 檔案選單
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Project (.mtvb)", command=self.dummy_action)
        file_menu.add_command(label="Open Project", command=self.dummy_action)
        file_menu.add_command(label="Save", command=self.dummy_action)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # 設定選單 (模型選擇)
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Model Selection (Default: 27B)", command=self.dummy_action)
        settings_menu.add_command(label="Container Settings", command=self.dummy_action)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        self.root.config(menu=menubar)

    def _init_top_bar(self):
        # 頂部全域指標工具列
        top_frame = ttk.Frame(self.root, padding="5")
        top_frame.pack(side=tk.TOP, fill=tk.X)

        # 模擬一些全域指標
        metrics = [
            ("Total LoC (log):", "3.45"),
            ("Test Coverage:", "82%"),
            ("Est. Progress:", "65%"),
            ("Token Budget:", "12k / 32k"),
            ("Container:", "Running (PID: 4096)")
        ]

        for label_text, value_text in metrics:
            container = ttk.Frame(top_frame, relief=tk.GROOVE, borderwidth=1)
            container.pack(side=tk.LEFT, padx=5, fill=tk.Y)
            ttk.Label(container, text=label_text, font=('Arial', 8, 'bold')).pack(side=tk.TOP, padx=5)
            ttk.Label(container, text=value_text, foreground="blue").pack(side=tk.BOTTOM, padx=5)

        # 快照/回滾按鈕
        ttk.Button(top_frame, text="Create Snapshot", command=self.dummy_action).pack(side=tk.RIGHT, padx=5)
        ttk.Button(top_frame, text="Undo/Rollback", command=self.dummy_action).pack(side=tk.RIGHT, padx=5)

    def _init_left_panel(self):
        left_frame = ttk.Frame(self.upper_horizontal_pane)
        self.upper_horizontal_pane.add(left_frame, width=250)

        ttk.Label(left_frame, text="Project Structure (Modules)", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=5)

        # 樹狀圖
        self.tree = ttk.Treeview(left_frame)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # 模擬數據
        root_node = self.tree.insert("", "end", text="Project Root", open=True)
        mod_a = self.tree.insert(root_node, "end", text="auth_module", open=True)
        self.tree.insert(mod_a, "end", text="login()")
        self.tree.insert(mod_a, "end", text="logout()")
        mod_b = self.tree.insert(root_node, "end", text="data_processor", open=True)
        self.tree.insert(mod_b, "end", text="parse_csv()")

        # 綁定右鍵選單
        self.tree.bind("<Button-3>", self.show_context_menu)

    def _init_center_panel(self):
        center_frame = ttk.Frame(self.upper_horizontal_pane)
        self.upper_horizontal_pane.add(center_frame, width=700)

        # --- 工作模式切換 (View Filters) ---
        mode_frame = ttk.Frame(center_frame)
        mode_frame.pack(fill=tk.X, pady=5)

        modes = ["Development", "Testing", "Debugging", "Structure Eval", "Gen Eval", "Optimization"]
        self.mode_vars = {}
        for mode in modes:
            var = tk.IntVar()
            chk = ttk.Checkbutton(mode_frame, text=mode, variable=var, style="Toolbutton") # Toolbutton 看起來像按鈕
            chk.pack(side=tk.LEFT, padx=2)
            self.mode_vars[mode] = var

        # --- 分頁工作區 ---
        self.notebook = ttk.Notebook(center_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: 藍圖/依賴圖 (Blueprint)
        self.tab_blueprint = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_blueprint, text="Blueprint (Graph)")
        # 這裡未來放 Canvas 畫圖
        self.canvas = tk.Canvas(self.tab_blueprint, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_text(300, 200, text="[Dependency Graph Visualization Placeholder]", fill="gray")

        # Tab 2: 程式碼編輯器 (Code)
        self.tab_code = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_code, text="Code Editor")
        self.code_editor = scrolledtext.ScrolledText(self.tab_code, font=('Consolas', 10))
        self.code_editor.pack(fill=tk.BOTH, expand=True)
        self.code_editor.insert(tk.END, "# Python code will appear here...\ndef login():\n    pass")

    def _init_right_panel(self):
        right_frame = ttk.Frame(self.upper_horizontal_pane)
        self.upper_horizontal_pane.add(right_frame, width=350)

        # 內部垂直分割
        right_pane = tk.PanedWindow(right_frame, orient=tk.VERTICAL)
        right_pane.pack(fill=tk.BOTH, expand=True)

        # --- 上半部：AI 思考與對話 ---
        ai_frame = ttk.LabelFrame(right_pane, text="AI Thought Process / Chat")
        right_pane.add(ai_frame, height=300)
        self.chat_log = scrolledtext.ScrolledText(ai_frame, state='disabled', height=10, font=('Arial', 9))
        self.chat_log.pack(fill=tk.BOTH, expand=True)

        # --- 下半部：深度指標 (Semantic Metrics) ---
        metrics_frame = ttk.LabelFrame(right_pane, text="Deep Semantic Metrics")
        right_pane.add(metrics_frame)

        # 模擬指標顯示
        labels = [
            ("Semantic Error:", "Low (0.12)", "green"),
            ("Model Entropy:", "High (Warning)", "orange"),
            ("Intent Points Cost:", "15 pts", "black"),
            ("Context Complexity:", "Medium", "blue")
        ]

        for text, val, color in labels:
            f = ttk.Frame(metrics_frame)
            f.pack(fill=tk.X, pady=2)
            ttk.Label(f, text=text).pack(side=tk.LEFT)
            ttk.Label(f, text=val, foreground=color).pack(side=tk.RIGHT)

    def _init_bottom_input_panel(self):
        input_frame = ttk.Frame(self.bottom_horizontal_pane)
        self.bottom_horizontal_pane.add(input_frame, width=600)

        # 主需求
        ttk.Label(input_frame, text="Main Requirement / Global Intent:").pack(anchor=tk.W)
        self.main_req_text = tk.Text(input_frame, height=4)
        self.main_req_text.pack(fill=tk.X, padx=5, pady=2)

        # 按鈕區
        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Generate Blueprint", command=self.dummy_action).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refine & Code", command=self.dummy_action).pack(side=tk.LEFT, padx=5)

        # 模組管理器 (簡單列表)
        ttk.Label(input_frame, text="Module Manager (Auto-filled by Blueprint):").pack(anchor=tk.W)
        self.mod_list = tk.Listbox(input_frame, height=5)
        self.mod_list.pack(fill=tk.BOTH, expand=True, padx=5)
        self.mod_list.insert(1, "Module: auth | Req: Handle JWT tokens")
        self.mod_list.insert(2, "Module: db | Req: SQLite connection")

    def _init_bottom_terminal_panel(self):
        term_frame = ttk.Frame(self.bottom_horizontal_pane)
        self.bottom_horizontal_pane.add(term_frame)

        ttk.Label(term_frame, text="Container Terminal / Execution Log").pack(anchor=tk.W)
        self.terminal = scrolledtext.ScrolledText(term_frame, bg="black", fg="white", font=('Consolas', 9))
        self.terminal.pack(fill=tk.BOTH, expand=True)
        self.terminal.insert(tk.END, "user@vibe-coder-container:~$ ready\n")

    def _init_status_bar(self):
        status = ttk.Label(self.root, text="System Ready | .mtvb project loaded", relief=tk.SUNKEN, anchor=tk.W)
        status.pack(side=tk.BOTTOM, fill=tk.X)

    def dummy_action(self):
        messagebox.showinfo("Info", "Backend logic not implemented yet.")

    def show_context_menu(self, event):
        # 樹狀圖右鍵選單
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Add Local Requirement", command=self.dummy_action)
        menu.add_command(label="Modify Logic", command=self.dummy_action)
        menu.add_separator()
        menu.add_command(label="Delete Module/Function", command=self.dummy_action)
        menu.post(event.x_root, event.y_root)

if __name__ == "__main__":
    root = tk.Tk()
    app = VibeCoderGUI(root)
    root.mainloop()
