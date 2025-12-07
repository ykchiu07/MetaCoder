import tkinter as tk
from tkinter import ttk, scrolledtext

class IntelligencePanel:
    def __init__(self, parent, mediator):
        self.mediator = mediator
        # 獲取由 MainWindow 傳遞的顏色配置
        colors = getattr(mediator, 'colors', {'bg': '#333', 'fg': '#eee', 'console_bg': '#1e1f22'})

        self.frame = ttk.LabelFrame(parent, text="Vibe Intelligence")

        # Log 區域 (暗色配置)
        self.log_area = scrolledtext.ScrolledText(
            self.frame,
            height=20,
            bg=colors['console_bg'],
            fg="#00ff00", # Hacker Green
            font=("Consolas", 9),
            insertbackground="white", # 游標顏色
            selectbackground="#214283"
        )
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def log(self, msg):
        """
        [修復] 這是之前遺失的關鍵方法。
        負責將訊息寫入 ScrolledText 元件。
        """
        # 使用 tk.END 插入到最後
        self.log_area.insert(tk.END, f"> {msg}\n")
        # 自動捲動到底部
        self.log_area.see(tk.END)

    def on_diagnose(self):
        """
        執行診斷邏輯
        需要從 WorkSpace 獲取當前程式碼 -> 呼叫 Backend -> 顯示結果
        """
        # 1. 跨元件獲取程式碼 (透過 Mediator)
        # MainWindow -> WorkSpace -> CodeEditor
        try:
            code = self.mediator.workspace.code_editor.get("1.0", tk.END).strip()
            # 簡單假設目前選中的是目標函式 (這裡可以優化為從 ProjectExplorer 獲取名稱)
            # 暫時用 "unknown_func" 或讓使用者輸入，這裡先寫死測試用
            func_name = "complex_logic"
        except Exception:
            code = ""
            func_name = "unknown"

        if not code:
            self.log("[Warn] Editor is empty. Nothing to diagnose.")
            return

        def task():
            self.mediator.log(f"Running Diagnostics on {func_name}...")

            # 呼叫 MetaCoder 的動態分析
            # 注意：這裡假設代碼可以直接執行 (self-contained)
            report = self.mediator.meta.run_dynamic_analysis(code, func_name)

            # 格式化輸出報告
            output = f"\n=== DIAGNOSTIC REPORT: {func_name} ===\n"
            output += f"Entropy (Logic): {report['entropies'][0]}\n"
            output += f"Entropy (Vision): {report['entropies'][1]}\n\n"

            output += "--- Logic Bottlenecks ---\n"
            output += report['logic_report'] + "\n"

            if report['vision_report']:
                output += "\n--- Visual Analysis ---\n"
                output += report['vision_report'] + "\n"

            self.mediator.log(output)

        # 透過 Mediator 執行非同步任務
        self.mediator.run_async(task)
