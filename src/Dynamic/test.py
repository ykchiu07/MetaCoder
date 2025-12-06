import json
import os
# from MetricCollector import MetricCollector
# from RuntimeAnalyst import RuntimeAnalyst

# 模擬一個使用者代碼執行場景 (同之前的 MetricCollector 測試)
# ... (省略 user_code 定義，假設已執行並產出數據) ...

def test_full_analysis_cycle():
    print("=== 1. Collecting Metrics ===")
    collector = MetricCollector()

    # 執行一段有 GUI 和 IO 的程式碼 (請貼上之前那個 complex_logic 的範例)
    user_code = """
import tkinter as tk
import time
def complex_logic(n):
    res = 0
    for i in range(1000): # Hotspot
        if i % 2 == 0: res += i
        else: res -= 1
    time.sleep(0.1) # Simulate delay
    return res

def main():
    root = tk.Tk()
    root.title("Bottleneck Test")
    label = tk.Label(root, text="Processing...")
    label.pack()
    root.update()

    complex_logic(5)

    with open("data.bin", "wb") as f: f.write(b"x"*1024) # IO

    time.sleep(0.5)

main()
"""
    collector.execute_code(user_code)

    # 獲取過濾後的原始數據
    target_func = "complex_logic"
    raw_json = collector.outputMetricResult(target_funcs=[target_func])
    data = json.loads(raw_json)

    print(f"Metrics collected for: {target_func}")

    print("\n=== 2. Starting Runtime Analyst ===")
    analyst = RuntimeAnalyst()

    # A. 執行瓶頸分析 (使用 12b 模型)
    print(">>> Analyzing Bottlenecks...")
    report_logic = analyst.analyzeBottleNeck(
        func_name=target_func,
        perf_data=data["performance"],
        io_data=data["io_activity"],
        coverage_data=data["code_coverage"],
        calls_data=data["call_graph"],
        logic_model="gemma3:12b"
    )
    print("--- Logic Report ---")
    print(report_logic)

    # B. 執行視覺分析 (使用 4b Vision 模型)
    # 檢查是否有截圖
    screenshots = data.get("gui_screenshots", [])
    if screenshots:
        print("\n>>> Analyzing GUI Snapshot...")
        report_vision = analyst.analyzeSnapshot(
            screenshot_path=screenshots[0],
            func_description="A window showing processing status.",
            user_report="The window background should be blue, but it looks default gray.",
            vision_model="gemma3:4b"
        )
        print("--- Vision Report ---")
        print(report_vision)
    else:
        print("\n[!] No screenshots found to analyze.")

if __name__ == "__main__":
    test_full_analysis_cycle()
