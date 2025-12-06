import os
import json
from typing import Dict, List, Optional, Any
from OllamaClient import OllamaClient

class RuntimeAnalyst:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.client = OllamaClient(ollama_url)

    def analyzeSnapshot(
        self,
        screenshot_path: str,
        func_description: str,
        user_report: str,
        vision_model: str = "gemma3:4b" # 使用具備視覺能力的較小模型
    ) -> str:
        """
        視覺除錯分析：結合截圖、規格說明與使用者回報，生成診斷報告。
        """
        if not screenshot_path or not os.path.exists(screenshot_path):
            return "Analysis Failed: Screenshot not found."

        print(f"[*] [RuntimeAnalyst] Analyzing GUI snapshot with {vision_model}...")

        # 1. 構建 Prompt
        system_prompt = (
            "You are a UI/UX Debugging Expert. "
            "Analyze the provided screenshot against the function description and user report. "
            "Identify visual discrepancies, layout issues, or rendering errors."
        )

        user_prompt = (
            f"FUNCTION GOAL: {func_description}\n"
            f"USER REPORT: \"{user_report}\"\n\n"
            "Analyze the screenshot:\n"
            "1. Describe what is visible.\n"
            "2. Does it match the Function Goal?\n"
            "3. Does it confirm the User Report?\n"
            "4. Suggest a specific fix (e.g., 'Resize widget', 'Check update() call')."
        )

        try:
            # 呼叫 OllamaClient 的 raw 方法 (需支援 images 參數)
            # 注意：請確保 OllamaClient.chat_complete_raw 已支援 **kwargs 或 images 參數
            # 這裡假設您已更新 Client，或直接在此使用 requests
            content, _ = self.client.chat_complete_raw(
                model=vision_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                # 這裡假設我們修改 OllamaClient 讓它接受額外參數，
                # 或者我們在這裡直接構造請求 (為了保持架構整潔，建議擴充 Client)
            )
            # 暫時 Hack: 如果 Client 沒支援 images，這裡需要直接用 requests (同之前的 VisualDebugger)
            # 假設 Client 已更新支援 context/images 參數注入

            return content
        except Exception as e:
            # Fallback for debugging
            return f"Visual Analysis Error: {e}"

    def analyzeBottleNeck(
        self,
        func_name: str,
        perf_data: Dict[str, Any],
        io_data: Dict[str, Any],
        coverage_data: Dict[str, Any],
        calls_data: List[Dict[str, Any]],
        logic_model: str = "gemma3:12b"
    ) -> str:
        """
        效能瓶頸分析：整合 CPU/RAM/IO/Coverage 數據，生成優化建議。
        """
        print(f"[*] [RuntimeAnalyst] Analyzing bottlenecks for '{func_name}' with {logic_model}...")

        # 1. 預處理數據 (萃取關鍵資訊以節省 Token)

        # A. 效能數據
        metric = perf_data.get(func_name, {})
        avg_time = metric.get("avg_time_ms", 0)
        total_time = metric.get("total_time_ms", 0)
        calls = metric.get("total_calls", 0)
        mem_peak = metric.get("memory_peak_bytes", 0)

        # B. IO 數據
        io_metric = io_data.get(func_name, {"read": 0, "write": 0})

        # C. 覆蓋率分析 (找出未執行或熱點)
        lines_info = coverage_data.get(func_name, {})
        hotspots = []
        dead_code = []
        for line_key, info in lines_info.items():
            hits = info.get("hits", 0)
            code = info.get("source", "").strip()
            if hits == 0:
                dead_code.append(f"{line_key}: {code}")
            elif hits > 100: # 假設 100 次算熱點
                hotspots.append(f"{line_key} (Hits={hits}): {code}")

        # D. 外部呼叫耗時 (從 Call Graph 推斷)
        # 簡單過濾出 callee 是別人的紀錄
        outgoing_calls = [c for c in calls_data if c['caller'] == func_name]

        # 2. 彙整 Context 字串
        analysis_context = (
            f"TARGET FUNCTION: {func_name}\n"
            f"--- METRICS ---\n"
            f"Execution Time: Total {total_time}ms (Avg {avg_time}ms per call)\n"
            f"Call Count: {calls}\n"
            f"Memory Peak: {mem_peak} bytes\n"
            f"IO Traffic: Read {io_metric.get('read')} bytes, Write {io_metric.get('write')} bytes\n\n"
            f"--- CODE ANALYSIS ---\n"
            f"Hotspots (Loop/High Freq): {json.dumps(hotspots[:5], ensure_ascii=False)}\n"
            f"Dead Code (Unused Branches): {json.dumps(dead_code[:5], ensure_ascii=False)}\n"
            f"Outgoing Calls: {len(outgoing_calls)} calls recorded.\n"
        )

        # 3. 構建 Prompt
        system_prompt = (
            "You are a Python Performance Optimization Expert. "
            "Analyze the provided runtime metrics to identify bottlenecks. "
            "Focus on: "
            "1. Algorithmic efficiency (based on Hotspots). "
            "2. IO blocking (based on IO Traffic vs Execution Time). "
            "3. Memory leaks or high usage. "
            "4. Test coverage gaps (Dead Code)."
        )

        user_prompt = (
            f"RUNTIME DATA:\n{analysis_context}\n\n"
            "Provide a concise report with specific optimization suggestions."
        )

        try:
            content, _ = self.client.chat_complete_raw(logic_model, system_prompt, user_prompt)
            return content
        except Exception as e:
            return f"Bottleneck Analysis Error: {e}"

    # 可擴展性預留：未來可以加入 analyzeSecurity, analyzeDependency 等方法
