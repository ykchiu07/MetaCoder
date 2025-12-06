import sys
import time
import tracemalloc
import builtins
import os
import tkinter
import importlib
from typing import Dict, List, Any
from dataclasses import dataclass
from collections import defaultdict # 記得 import 這個
import json

try:
    from PIL import ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# --- 新增：DPI 感知 (保持不變) ---
def _set_dpi_awareness():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except: pass

@dataclass
class FunctionMetric:
    func_name: str
    call_count: int = 0
    total_time_ms: float = 0.0
    memory_peak_bytes: int = 0
    io_read_bytes: int = 0
    io_write_bytes: int = 0

@dataclass
class CallRecord:
    caller: str
    callee: str
    elapsed_time_sec: float

class FileProxy:
    def __init__(self, real_file, collector):
        self._real_file = real_file
        self._collector = collector
    def read(self, size=-1):
        data = self._real_file.read(size)
        if data: self._collector._record_io(read=len(str(data)))
        return data
    def write(self, data):
        if data: self._collector._record_io(write=len(str(data)))
        return self._real_file.write(data)
    def __getattr__(self, name): return getattr(self._real_file, name)
    def __enter__(self): self._real_file.__enter__(); return self
    def __exit__(self, exc_type, exc_val, exc_tb): return self._real_file.__exit__(exc_type, exc_val, exc_tb)

class MetricCollector:
    def __init__(self):
        self._reset_state()
        self._orig_tk_methods = {}
        self._orig_open = None

    def _reset_state(self):
        self.metrics = {}
        self.call_history = []
        self.screenshots = []
        self._current_function_stack = []
        self._start_times = {}
        self._mem_snapshots = {}
        self._exec_start_time = 0.0
        self._last_snap_time = 0.0
        self._screenshot_interval = 1.0

        # [修正] 初始化原始碼儲存列表與計數器
        self._source_code_lines: List[str] = []
        self._line_hit_counts: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))

    def _get_metric(self, name):
        if name not in self.metrics: self.metrics[name] = FunctionMetric(name)
        return self.metrics[name]

    def _record_io(self, read=0, write=0):
        if self._current_function_stack:
            m = self._get_metric(self._current_function_stack[-1])
            m.io_read_bytes += read
            m.io_write_bytes += write

    def _tracer(self, frame, event, arg):
        code = frame.f_code
        fname = code.co_name

        # 排除自身
        if "MetricCollector" in str(code.co_filename) or fname.startswith("_"):
            return self._tracer

        now = time.time()

        # [功能] 覆蓋率計算
        if event == 'line':
            line_no = frame.f_lineno
            self._line_hit_counts[fname][line_no] += 1
            return self._tracer

        if event == 'call':
            caller = self._current_function_stack[-1] if self._current_function_stack else "root"
            self.call_history.append(CallRecord(caller, fname, round(now - self._exec_start_time, 6)))
            self._current_function_stack.append(fname)
            self._start_times[fname] = now
            self._mem_snapshots[fname] = tracemalloc.get_traced_memory()[0]
            self._get_metric(fname).call_count += 1
            return self._tracer # 必須回傳 tracer 以啟用 line 事件

        elif event == 'return':
            if self._current_function_stack and self._current_function_stack[-1] == fname:
                self._current_function_stack.pop()
                dur = (now - self._start_times.get(fname, now)) * 1000
                m = self._get_metric(fname)
                m.total_time_ms += dur
                peak = max(0, tracemalloc.get_traced_memory()[0] - self._mem_snapshots.get(fname, 0))
                if peak > m.memory_peak_bytes: m.memory_peak_bytes = peak
            return self._tracer

        return self._tracer

    def _snapshot(self, root):
        if not HAS_PIL: return
        now = time.time()
        if now - self._last_snap_time < self._screenshot_interval: return
        try:
            if not root.winfo_exists(): return
            root.update_idletasks() # 關鍵：同步座標
            x, y = root.winfo_rootx(), root.winfo_rooty()
            w, h = root.winfo_width(), root.winfo_height()

            # Linux 邊框修正邏輯 (視需要啟用)
            # if sys.platform == "linux": y -= 30

            if w > 10 and h > 10:
                fname = os.path.abspath(f"gui_snap_{int(now*1000)}.png")
                # 如果是 Linux 且有安裝 import，可考慮用 os.system(f"import -window {root.winfo_id()} ...")
                # 這裡預設使用 PIL
                import PIL.ImageGrab
                PIL.ImageGrab.grab(bbox=(x, y, x+w, y+h)).save(fname)
                if os.path.exists(fname):
                    self.screenshots.append(fname)
                    self._last_snap_time = now
        except: pass

    def _patch_tkinter(self):
        if not isinstance(tkinter.Tk, type): importlib.reload(tkinter)
        tk = tkinter.Tk
        self._orig_tk_methods = {'update': tk.update, 'mainloop': tk.mainloop}

        def hooked_update(self_tk):
            self._orig_tk_methods['update'](self_tk)
            self._snapshot(self_tk)

        def hooked_mainloop(self_tk, *args, **kwargs):
            def scheduled_snapshot():
                if self_tk.winfo_exists():
                    self._snapshot(self_tk)
                    self_tk.after(1000, scheduled_snapshot)
            scheduled_snapshot()
            self._orig_tk_methods['mainloop'](self_tk, *args, **kwargs)

        tk.update = hooked_update
        tk.mainloop = hooked_mainloop

    def _unpatch_tkinter(self):
        tk = tkinter.Tk
        if self._orig_tk_methods:
            tk.update = self._orig_tk_methods['update']
            tk.mainloop = self._orig_tk_methods['mainloop']
        self._orig_tk_methods = {}

    def _hook_open(self, orig_open):
        def hooked(file, mode='r', *args, **kwargs):
            return FileProxy(orig_open(file, mode, *args, **kwargs), self)
        return hooked

    def execute_code(self, code_str: str):
        _set_dpi_awareness()
        self._reset_state()

        # --- [修正] 關鍵的一行：填充原始碼列表 ---
        # 處理 user_code 開頭可能的空白行，確保行號對齊
        self._source_code_lines = code_str.splitlines()

        tracemalloc.start()
        self._orig_open = builtins.open
        builtins.open = self._hook_open(self._orig_open)
        self._patch_tkinter()
        self._exec_start_time = time.time()
        sys.settrace(self._tracer)

        global_scope = {"__name__": "__main__", "tk": tkinter, "tkinter": tkinter}

        try:
            print("[MetricCollector] Executing user code...")
            exec(code_str, global_scope)
        except Exception as e:
            print(f"[MetricCollector] Runtime Error: {e}")
        finally:
            sys.settrace(None)
            if self._orig_open: builtins.open = self._orig_open
            self._unpatch_tkinter()
            tracemalloc.stop()
            print("[MetricCollector] Analysis finished.")

    # --- APIs ---
    def getBenchmarkData(self):
        res = {}
        for n, m in self.metrics.items():
            avg = m.total_time_ms / m.call_count if m.call_count else 0
            res[n] = {"calls": m.call_count, "time_ms": round(m.total_time_ms, 4), "avg_ms": round(avg, 4), "mem_peak": m.memory_peak_bytes}
        return res
    def getCallHistory(self): return [vars(c) for c in self.call_history]
    def getIOHistory(self): return {n: {"r": m.io_read_bytes, "w": m.io_write_bytes} for n, m in self.metrics.items() if m.io_read_bytes or m.io_write_bytes}
    def getGUIScreenshot(self): return self.screenshots

    # --- [功能] 獲取覆蓋率報告 ---
    def getCodeCoverage(self) -> Dict[str, Any]:
        coverage_report = {}
        for func_name, line_hits in self._line_hit_counts.items():
            func_report = {}
            for line_no, count in line_hits.items():
                code_content = "<unknown>"
                # 修正索引：行號從 1 開始，List 索引從 0 開始
                if 0 <= line_no - 1 < len(self._source_code_lines):
                    code_content = self._source_code_lines[line_no - 1].strip()

                func_report[f"line_{line_no}"] = {
                    "source": code_content,
                    "hits": count,
                    "type": "loop_hotspot" if count > 1 else "visited"
                }
            coverage_report[func_name] = func_report
        return coverage_report

    # --- [功能] 標準化輸出 ---
    def outputMetricResult(self, target_funcs: List[str] = None) -> str:
        """
        將收集到的數據打包成 JSON。
        Args:
            target_funcs: 若指定，則只輸出這些函式的數據 (例如 ["complex_logic"])。
                          若為 None 或空，則輸出全部。
        """

        # 輔助過濾函式
        def filter_dict(source_dict):
            if not target_funcs: return source_dict
            return {k: v for k, v in source_dict.items() if k in target_funcs}

        # 針對 Call Graph 的特殊過濾 (只保留 caller 或 callee 在目標清單中的紀錄)
        filtered_calls = self.getCallHistory()
        if target_funcs:
            filtered_calls = [
                c for c in filtered_calls
                if c['caller'] in target_funcs or c['callee'] in target_funcs
            ]

        final_report = {
            "meta": {
                "timestamp": time.time(),
                "platform": sys.platform,
                "filter_applied": target_funcs if target_funcs else "ALL"
            },
            "performance": filter_dict(self.getBenchmarkData()),
            "io_activity": filter_dict(self.getIOHistory()),
            "code_coverage": filter_dict(self.getCodeCoverage()),
            "call_graph": filtered_calls,
            # Screenshot 是全域的，無法依函式過濾，故保留
            "gui_screenshots": self.getGUIScreenshot(),
        }

        return json.dumps(final_report, indent=2, ensure_ascii=False)
