import os
import json
from typing import Dict, List, Optional, Any, Tuple
import sys
sys.path.append("Generate")
from OllamaClient import OllamaClient

class RuntimeAnalyst:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.client = OllamaClient(ollama_url)

    def analyzeSnapshot(
        self,
        screenshot_path: str,
        func_description: str,
        user_report: str,
        vision_model: str = "gemma3:4b"
    ) -> Tuple[str, float]: # [修正] 回傳 Tuple
        """
        視覺除錯分析
        """
        if not screenshot_path or not os.path.exists(screenshot_path):
            return "Analysis Failed: Screenshot not found.", 0.0

        print(f"[*] [RuntimeAnalyst] Analyzing GUI snapshot with {vision_model}...")

        # [修正] Prompt：強制簡潔正式
        system_prompt = (
            "You are a strict UI Verification Engine. "
            "Analyze the GUI screenshot based on the User Report. "
            "\n\n"
            "CRITICAL FORMATTING RULES:\n"
            "1. Output ONLY the analysis list. DO NOT generate document headers, dates, IDs, or introductory text.\n"
            "2. For each distinct issue or element, use the following EXACT format block:\n"
            "\n"
            "### ELEMENT: <Name of the UI component (e.g., 'Progress Bar', 'Save Button')>\n"
            "1. VISUAL_OBSERVATION: <What you see pixels-wise>\n"
            "2. SPEC_CHECK: <Pass/Fail>\n"
            "3. ISSUE_VERIFICATION: <Confirmed/Denied based on user report>\n"
            "4. FIX_SUGGESTION: <Specific fix>\n"
            "\n"
            "3. If multiple issues exist, repeat the block for each one."
        )

        user_prompt = (
            f"FUNCTION_GOAL: {func_description}\n"
            f"USER_REPORT: {user_report}\n"
            "Analyze the attached screenshot."
        )

        # 呼叫更新後的 Client (會自動處理 Base64)
        content, entropy = self.client.chat_complete_raw(
            model=vision_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            images=[screenshot_path]
        )
        return content, entropy

    def analyzeBottleNeck(
        self,
        func_name: str,
        perf_data: Dict[str, Any],
        io_data: Dict[str, Any],
        coverage_data: Dict[str, Any],
        calls_data: List[Dict[str, Any]],
        logic_model: str = "gemma3:12b"
    ) -> Tuple[str, float]: # [修正] 回傳 Tuple
        """
        效能瓶頸分析
        """
        print(f"[*] [RuntimeAnalyst] Analyzing bottlenecks for '{func_name}' with {logic_model}...")

        # A. 效能數據 (增加防禦性檢查，避免 Zero Call Count 誤判)
        metric = perf_data.get(func_name)
        if metric is None:
            # 如果找不到該函式的數據，直接回傳錯誤，不要讓 LLM 瞎掰
            return f"Error: No performance data found for function '{func_name}'. Check function name spelling.", 0.0

        avg_time = metric.get("avg_time_ms", 0)
        total_time = metric.get("total_time_ms", 0)
        calls = metric.get("total_calls", 0)
        mem_peak = metric.get("memory_peak_bytes", 0)

        # B. IO 數據
        io_metric = io_data.get(func_name, {"read": 0, "write": 0})

        # C. 覆蓋率分析
        lines_info = coverage_data.get(func_name, {})
        hotspots = []
        dead_code = []
        # 簡單過濾，只取前 3 個熱點以節省 Context
        sorted_lines = sorted(lines_info.items(), key=lambda x: x[1]['hits'], reverse=True)
        for line_key, info in sorted_lines:
            hits = info.get("hits", 0)
            code = info.get("source", "").strip()
            if hits == 0:
                dead_code.append(f"{line_key}: {code}")
            elif hits > 50: # 門檻值
                hotspots.append(f"{line_key} (Hits={hits}): {code}")

        # D. 外部呼叫
        outgoing_calls = [c for c in calls_data if c['caller'] == func_name]

        # 2. 彙整 Context 字串
        analysis_context = (
            f"TARGET: {func_name}\n"
            f"METRICS: Time={total_time}ms (Avg {avg_time}ms), Calls={calls}, MemPeak={mem_peak}B\n"
            f"IO: R={io_metric.get('read')}B, W={io_metric.get('write')}B\n"
            f"HOTSPOTS (Top 5): {json.dumps(hotspots[:5], ensure_ascii=False)}\n"
            f"DEAD_CODE (Top 5): {json.dumps(dead_code[:5], ensure_ascii=False)}\n"
            f"OUTGOING_CALLS: {len(outgoing_calls)}\n"
        )

        # [修正] Prompt：強制簡潔正式
        system_prompt = (
            "You are a Kernel Profiling Expert. "
            "Output a concise performance diagnosis. "
            "NO conversational filler. "
            "Format strictly as:\n"
            "1. BOTTLENECK_ID: <Loop/IO/Memory/Logic>\n"
            "2. SEVERITY: <High/Medium/Low>\n"
            "3. ROOT_CAUSE: <Technical explanation based on metrics>\n"
            "4. OPTIMIZATION: <Specific Code/Architecture change>"
        )

        user_prompt = (
            f"DATA:\n{analysis_context}\n\n"
            "Diagnose performance."
        )

        content, entropy = self.client.chat_complete_raw(logic_model, system_prompt, user_prompt)
        return content, entropy
