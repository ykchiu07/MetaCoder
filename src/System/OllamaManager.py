import subprocess
import time
import os
import signal
import sys
import requests

class OllamaManager:
    def __init__(self):
        self.process = None
        self.log_func = print # 預設輸出到 console，稍後由 MetaCoder 覆蓋

    def set_logger(self, func):
        self.log_func = func

    def is_running(self):
        """檢查 Ollama 服務是否回應"""
        try:
            # 嘗試連線一個輕量級 API
            requests.get("http://localhost:11434/api/tags", timeout=1)
            return True
        except:
            return False

    def start_service(self):
        """啟動 ollama serve"""
        if self.is_running():
            self.log_func("[OllamaManager] Service already running.")
            return

        self.log_func("[OllamaManager] Starting 'ollama serve'...")
        try:
            # 使用 shell=True 在某些環境下比較容易抓到 path，但要小心子進程管理
            # 這裡使用 creationflags 確保可以殺乾淨 (Windows)
            kwargs = {}
            if sys.platform == "win32":
                kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP

            self.process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **kwargs
            )

            # 等待服務就緒
            for _ in range(10): # 最多等 10 秒
                if self.is_running():
                    self.log_func("[OllamaManager] Service is READY.")
                    return
                time.sleep(1)

            self.log_func("[OllamaManager] Warning: Service start timed out, but proceeding.")

        except Exception as e:
            self.log_func(f"[OllamaManager] Start failed: {e}")

    def kill_service(self):
        """核選項：殺死進程"""
        self.log_func("[OllamaManager] KILLING Ollama Service...")

        # 1. 先殺 Python 掌握的子進程
        if self.process:
            try:
                self.process.kill() # SIGKILL
                self.process.terminate()
            except: pass
            self.process = None

        # 2. 系統級強制清理 (防止殭屍進程或早已存在的服務)
        try:
            if sys.platform == "win32":
                os.system("taskkill /F /IM ollama.exe /T")
                os.system("taskkill /F /IM ollama_app.exe /T") # 有些版本叫這個
            else:
                os.system("pkill -9 ollama")
        except Exception as e:
            self.log_func(f"[OllamaManager] System kill failed: {e}")

        self.log_func("[OllamaManager] Service TERMINATED.")
