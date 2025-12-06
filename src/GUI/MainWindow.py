import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import os
from ProjectExplorer import ProjectExplorer
from WorkSpace import WorkSpace
from IntelligencePanel import IntelligencePanel
from ControlPanel import ControlPanel

class MainWindow:
    def __init__(self, root, meta_coder):
        self.root = root
        self.meta = meta_coder

        self.root.title("Vibe-Coder IDE (Dark Edition)")
        self.root.geometry("1400x900")

        # 任務管理相關
        self._current_cancel_flag = threading.Event()
        self._is_task_running = False

        # 1. 套用暗色主題 (必須在元件建立前設定 Style)
        self._apply_dark_theme()

        # 2. 初始化佈局
        self._init_layout()

        # 3. 初始化選單
        self._init_menu()

    def _apply_dark_theme(self):
        """手工打造的暗色主題引擎"""
        style = ttk.Style()
        style.theme_use('clam') # clam 引擎最容易自定義顏色

        # 定義色票 (Darcula 風格)
        bg_dark = "#2b2b2b"
        bg_lighter = "#3c3f41"
        fg_text = "#a9b7c6"
        accent = "#4a88c7" # 藍色強調
        sel_bg = "#214283"

        # 設定全域樣式
        style.configure(".", background=bg_dark, foreground=fg_text, borderwidth=0)
        style.configure("TFrame", background=bg_dark)
        style.configure("TLabelframe", background=bg_dark, foreground=fg_text, bordercolor=bg_lighter)
        style.configure("TLabelframe.Label", background=bg_dark, foreground=fg_text)

        # 按鈕樣式
        style.configure("TButton", background=bg_lighter, foreground=fg_text, borderwidth=1, focuscolor=accent)
        style.map("TButton", background=[("active", "#4c5052"), ("pressed", "#5c6062")])

        # Treeview (最難搞的部分)
        style.configure("Treeview",
                        background=bg_lighter,
                        foreground=fg_text,
                        fieldbackground=bg_lighter,
                        borderwidth=0)
        style.map("Treeview", background=[("selected", sel_bg)])

        # Notebook (頁籤)
        style.configure("TNotebook", background=bg_dark)
        style.configure("TNotebook.Tab", background=bg_lighter, foreground=fg_text, padding=[10, 2])
        style.map("TNotebook.Tab", background=[("selected", bg_dark)], foreground=[("selected", "#ffffff")])

        # PanedWindow
        style.configure("TPanedwindow", background=bg_dark)
        style.configure("Sash", sashthickness=2, background="#555555")

        # 設定 root 背景，防止閃爍
        self.root.configure(bg=bg_dark)

        # 保存顏色供非 ttk 元件 (Text, Canvas) 使用
        self.colors = {
            "bg": bg_dark, "fg": fg_text,
            "editor_bg": "#1e1f22", "console_bg": "#1e1f22"
        }

    def _init_menu(self):
        menubar = tk.Menu(self.root, bg="#3c3f41", fg="#a9b7c6", activebackground="#4b6eaf", activeforeground="white")

        # --- 檔案 (File) ---
        file_menu = tk.Menu(menubar, tearoff=0, bg="#3c3f41", fg="#a9b7c6")
        file_menu.add_command(label="Open Workspace...", command=self.on_open_workspace)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # --- 編輯 (Edit) ---
        edit_menu = tk.Menu(menubar, tearoff=0, bg="#3c3f41", fg="#a9b7c6")
        edit_menu.add_command(label="Undo", command=lambda: self.log("Undo not impl"))
        edit_menu.add_command(label="Redo", command=lambda: self.log("Redo not impl"))
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # --- 檢視 (View) ---
        view_menu = tk.Menu(menubar, tearoff=0, bg="#3c3f41", fg="#a9b7c6")
        view_menu.add_command(label="Toggle Console", command=lambda: self.log("Toggle Console"))
        menubar.add_cascade(label="View", menu=view_menu)

        # --- 設定 (Settings) ---
        settings_menu = tk.Menu(menubar, tearoff=0, bg="#3c3f41", fg="#a9b7c6")
        settings_menu.add_command(label="Model Selection...", command=self.on_model_settings)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        # --- 說明 (Help) ---
        help_menu = tk.Menu(menubar, tearoff=0, bg="#3c3f41", fg="#a9b7c6")
        help_menu.add_command(label="About Vibe-Coder", command=lambda: messagebox.showinfo("About", "Vibe-Coder v0.2\nPowered by Ollama"))
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _init_layout(self):
        # 佈局程式碼維持不變，但傳入 self.colors 給子元件以便設定 Text 背景
        self.main_pane = tk.PanedWindow(self.root, orient=tk.VERTICAL, sashrelief=tk.FLAT, bg=self.colors['bg'])
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        self.top_pane = tk.PanedWindow(self.main_pane, orient=tk.HORIZONTAL, sashrelief=tk.FLAT, bg=self.colors['bg'])
        self.main_pane.add(self.top_pane, height=700)

        # 傳入 self (MainWindow) 讓子元件可以存取 colors 和 helper methods
        self.nav = ProjectExplorer(self.top_pane, self)
        self.top_pane.add(self.nav.frame, width=250)

        self.workspace = WorkSpace(self.top_pane, self)
        self.top_pane.add(self.workspace.frame, width=800)

        self.intelligence = IntelligencePanel(self.top_pane, self)
        self.top_pane.add(self.intelligence.frame, width=350)

        self.controls = ControlPanel(self.main_pane, self)
        self.main_pane.add(self.controls.frame)

    # --- 業務邏輯 ---

    def on_open_workspace(self):
        from tkinter import filedialog
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.log(f"Switched workspace to: {dir_path}")
            # 這裡應該重新初始化 MetaCoder，為了簡化我們先只做 Log
            # self.meta = MetaCoder(dir_path)
            # self.nav.refresh_tree()

    def on_model_settings(self):
        """彈出模型設定視窗"""
        win = tk.Toplevel(self.root)
        win.title("Model Configuration")
        win.geometry("400x300")
        win.configure(bg=self.colors['bg'])

        row = 0
        entries = {}
        for role, current_model in self.meta.model_config.items():
            lbl = tk.Label(win, text=f"{role.capitalize()} Model:", bg=self.colors['bg'], fg=self.colors['fg'])
            lbl.grid(row=row, column=0, padx=10, pady=10, sticky="w")

            ent = tk.Entry(win, bg="#555", fg="white")
            ent.insert(0, current_model)
            ent.grid(row=row, column=1, padx=10, pady=10, sticky="ew")
            entries[role] = ent
            row += 1

        def save():
            for role, ent in entries.items():
                self.meta.update_model_config(role, ent.get())
            win.destroy()
            self.log("Model settings updated.")

        tk.Button(win, text="Save", command=save, bg="#4a88c7", fg="white").grid(row=row, column=0, columnspan=2, pady=20)

    # --- 可中止的非同步執行器 (Cancellable Task Runner) ---

    def run_async(self, task_func, success_callback=None, error_callback=None, cancel_callback=None):
        """
        執行非同步任務，並支援中止。
        task_func: 耗時的函式，應該接受一個 'cancel_event' 參數 (如果支援的話)
        """
        if self._is_task_running:
            self.log("[System] A task is already running.")
            return

        self._current_cancel_flag.clear()
        self._is_task_running = True

        # 通知 ControlPanel 切換按鈕狀態
        self.controls.set_running_state(True)

        def wrapper():
            try:
                # 執行任務
                task_func()

                # 檢查是否被取消
                if self._current_cancel_flag.is_set():
                    if cancel_callback: self.root.after(0, cancel_callback)
                    self.log("[System] Task Cancelled.")
                else:
                    if success_callback: self.root.after(0, success_callback)
                    self.set_status("Ready")
            except Exception as e:
                self.log(f"[Error] {str(e)}")
                if error_callback: self.root.after(0, lambda: error_callback(e))
                self.set_status("Error Occurred")
            finally:
                self._is_task_running = False
                # 恢復按鈕狀態
                self.root.after(0, lambda: self.controls.set_running_state(False))

        threading.Thread(target=wrapper, daemon=True).start()

    def stop_current_task(self):
        """當使用者按下 Stop 時呼叫"""
        if self._is_task_running:
            self.log("[System] Stopping task...")
            self._current_cancel_flag.set()
            # 注意：Python Thread 無法強制殺死。
            # 我們只能設定 flag，讓 UI 進入"已取消"狀態，並忽略後續結果。
            # 若要真正中斷 LLM 請求，需要修改 OllamaClient 檢查這個 flag。

    # --- Helper Proxies ---
    def log(self, msg): self.intelligence.log(msg)
    def set_status(self, msg): self.controls.set_status(msg)
