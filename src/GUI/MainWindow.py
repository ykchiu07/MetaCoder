import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import queue
from ProjectExplorer import ProjectExplorer
from WorkSpace import WorkSpace
from IntelligencePanel import IntelligencePanel
from ControlPanel import ControlPanel

class MainWindow:
    def __init__(self, root, meta_coder):
        self.root = root
        self.meta = meta_coder

        # [UI Config]
        self.root.title("Vibe-Coder IDE") # 已移除 (Dark Mode)
        self.root.geometry("1400x900")

        # [Task Management]
        self._current_cancel_flag = threading.Event()
        self.task_queue = queue.Queue()
        self._is_worker_running = False
        self._queue_loop_running = False # 防止重複啟動 Loop

        # [Initialization]
        self._apply_dark_theme()
        self._init_layout()
        self._init_menu()

        # 啟動任務隊列監聽 (只啟動一次)
        self._start_queue_loop()

    def _apply_dark_theme(self):
        style = ttk.Style()
        style.theme_use('clam')

        bg_dark = "#2b2b2b"
        bg_lighter = "#3c3f41"
        fg_text = "#a9b7c6"
        accent = "#4a88c7"
        sel_bg = "#214283"

        style.configure(".", background=bg_dark, foreground=fg_text, borderwidth=0)
        style.configure("TFrame", background=bg_dark)
        style.configure("TLabelframe", background=bg_dark, foreground=fg_text, bordercolor=bg_lighter)
        style.configure("TLabelframe.Label", background=bg_dark, foreground=fg_text)
        style.configure("TButton", background=bg_lighter, foreground=fg_text, borderwidth=1, focuscolor=accent)
        style.map("TButton", background=[("active", "#4c5052"), ("pressed", "#5c6062")])

        style.configure("Treeview", background=bg_lighter, foreground=fg_text, fieldbackground=bg_lighter, borderwidth=0)
        style.map("Treeview", background=[("selected", sel_bg)])

        style.configure("TNotebook", background=bg_dark)
        style.configure("TNotebook.Tab", background=bg_lighter, foreground=fg_text, padding=[10, 2])
        style.map("TNotebook.Tab", background=[("selected", bg_dark)], foreground=[("selected", "#ffffff")])

        style.configure("TPanedwindow", background=bg_dark)
        style.configure("Sash", sashthickness=2, background="#555555")

        self.root.configure(bg=bg_dark)
        self.colors = {"bg": bg_dark, "fg": fg_text, "editor_bg": "#1e1f22", "console_bg": "#1e1f22"}

    def _init_layout(self):
        # 使用 PanedWindow 進行佈局
        self.main_pane = tk.PanedWindow(self.root, orient=tk.VERTICAL, sashrelief=tk.FLAT, bg=self.colors['bg'])
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        self.top_pane = tk.PanedWindow(self.main_pane, orient=tk.HORIZONTAL, sashrelief=tk.FLAT, bg=self.colors['bg'])
        self.main_pane.add(self.top_pane, height=700)

        # 左側導航
        self.nav = ProjectExplorer(self.top_pane, self)
        self.top_pane.add(self.nav.frame, width=250)

        # 中間工作區
        self.workspace = WorkSpace(self.top_pane, self)
        self.top_pane.add(self.workspace.frame, width=800)

        # 右側情報區
        self.intelligence = IntelligencePanel(self.top_pane, self)
        self.top_pane.add(self.intelligence.frame, width=350)

        # 下方控制區
        self.controls = ControlPanel(self.main_pane, self)
        self.main_pane.add(self.controls.frame)

    def _init_menu(self):
        menubar = tk.Menu(self.root, bg="#3c3f41", fg="#a9b7c6", activebackground="#4b6eaf", activeforeground="white")

        file_menu = tk.Menu(menubar, tearoff=0, bg="#3c3f41", fg="#a9b7c6")
        file_menu.add_command(label="Open Workspace...", command=self.on_open_workspace)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0, bg="#3c3f41", fg="#a9b7c6")
        edit_menu.add_command(label="Undo", command=lambda: self.log("Undo not implemented"))
        menubar.add_cascade(label="Edit", menu=edit_menu)

        settings_menu = tk.Menu(menubar, tearoff=0, bg="#3c3f41", fg="#a9b7c6")
        settings_menu.add_command(label="Model Selection...", command=self.on_model_settings)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        self.root.config(menu=menubar)

    # --- Task Queue System ---
    def _start_queue_loop(self):
        if self._queue_loop_running: return
        self._queue_loop_running = True
        self._check_queue_loop()

    def _check_queue_loop(self):
        # 簡單的 Keep-alive，實際執行由 Worker Thread 負責
        self.root.after(1000, self._check_queue_loop)

    def run_async(self, task_func, success_callback=None, error_callback=None, cancel_callback=None):
        # [Fix 3] 任務進來時，確保服務啟動
        # 注意：這可能會卡住 UI 一兩秒，最好放在 Worker 裡面做
        # 但為了簡單，我們在這裡呼叫，反正 OllamaManager 有 check running

        task_item = {
            'func': task_func,
            'success': success_callback,
            'error': error_callback,
            'cancel': cancel_callback
        }
        self.task_queue.put(task_item)

        if not self._is_worker_running:
            self._start_worker_thread()

    def _start_worker_thread(self):
        self._is_worker_running = True
        self.controls.set_running_state(True)

        def worker():

            # [Fix 3] Worker 啟動時確保 Ollama 活著
            self.log("[System] Ensuring Ollama service is running...")
            self.meta.ensure_ollama_started()

            while True:
                try:
                    # 阻塞式獲取，直到有任務或 timeout (讓出檢查 stop flag)
                    task_item = self.task_queue.get(timeout=1)
                except queue.Empty:
                    # 隊列空了，結束 worker
                    if self.task_queue.empty():
                        break
                    continue

                if self._current_cancel_flag.is_set():
                    # 清空剩餘任務
                    with self.task_queue.mutex:
                        self.task_queue.queue.clear()
                    self.log("[System] Remaining tasks cancelled.")
                    break

                try:
                    task_item['func']()

                    if self._current_cancel_flag.is_set():
                        if task_item['cancel']: self.root.after(0, task_item['cancel'])
                    else:
                        if task_item['success']: self.root.after(0, task_item['success'])
                        self.set_status("Ready")

                except Exception as e:
                    self.log(f"[Error] {e}")
                    if task_item['error']: self.root.after(0, lambda: task_item['error'](e))
                finally:
                    self.task_queue.task_done()

            self._is_worker_running = False
            self._current_cancel_flag.clear()
            self.root.after(0, lambda: self.controls.set_running_state(False))

        threading.Thread(target=worker, daemon=True).start()

    def stop_current_task(self):
        if self._is_worker_running:
            self.log("[System] NUCLEAR STOP DETECTED. Killing Ollama...")

            # [Fix 3] 核選項：先殺服務
            self.meta.kill_ollama()

            # 再設定旗標清空隊列
            self._current_cancel_flag.set()

    # --- Actions ---
    def on_open_workspace(self):
        from tkinter import filedialog
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.log(f"Switching workspace to: {dir_path}")
            self.meta.set_workspace(dir_path)
            self.nav.set_workspace(dir_path)

            # 清空 UI
            self.workspace.clear_all_editors()
            self.workspace.canvas.delete("all")

            self.root.title(f"Vibe-Coder IDE - {os.path.basename(dir_path)}")

    def on_model_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Model Configuration")
        win.geometry("400x300")
        win.configure(bg=self.colors['bg'])

        row = 0
        entries = {}
        for role, current_model in self.meta.model_config.items():
            tk.Label(win, text=f"{role.capitalize()} Model:", bg=self.colors['bg'], fg=self.colors['fg']).grid(row=row, column=0, padx=10, pady=10, sticky="w")
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

    # --- Helpers ---
    def log(self, msg): self.intelligence.log(msg)
    def set_status(self, msg): self.controls.set_status(msg)
