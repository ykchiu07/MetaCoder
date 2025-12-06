import os
import json
import time
import re
from typing import List, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from OllamaClient import OllamaClient

@dataclass
class ImplementationResult:
    function_name: str
    file_path: str
    model_entropy: float
    duration: float
    success: bool

class CodeImplementer:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.client = OllamaClient(ollama_url)

    def _extract_python_code(self, text: str) -> str:
        # 優先匹配 ```python ... ```
        match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if match: return match.group(1)
        # 其次匹配 ``` ... ```
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match: return match.group(1)
        return text

    def _implement_single_function(
        self,
        spec_data: Dict,
        func_name: str,
        module_dir: str,
        model_name: str= "gemma3:12b",
        feedback_report: str = None  # [新增] 接收來自 RuntimeAnalyst 的報告
    ) -> ImplementationResult:

        start_time = time.time()

        # 1. 推導路徑
        filename = "__init_logic__.py" if func_name == "__init__" else f"{func_name}.py"
        target_path = os.path.join(module_dir, filename)

        # 2. 獲取 Spec
        target_func_spec = next((f for f in spec_data.get('functions', []) if f['name'] == func_name), None)
        if not target_func_spec:
            return ImplementationResult(func_name, target_path, -1.0, 0.0, False)

        print(f"    > Processing {func_name} with {model_name} (Mode: {'FIX' if feedback_report else 'CREATE'})...")

        # 3. 準備 Context
        module_name = spec_data.get('module_name', 'unknown_module')
        func_signature = (
            f"Name: {target_func_spec['name']}\n"
            f"Args: {target_func_spec.get('args')}\n"
            f"Return: {target_func_spec.get('return_type')}\n"
            f"Description: {target_func_spec.get('docstring')}"
        )

        # [新增] 讀取現有程式碼 (如果是修復模式)
        existing_code = ""
        if feedback_report and os.path.exists(target_path):
            with open(target_path, 'r', encoding='utf-8') as f:
                existing_code = f.read()

        # 4. 動態構建 Prompt
        if feedback_report:
            # --- FIX MODE PROMPT ---
            system_prompt = (
                "You are an expert Python Developer tasked with FIXING code based on a bug/chaos report. "
                "1. Read the REPORT and the EXISTING CODE. "
                "2. Output the FULLY CORRECTED code. "
                "3. Fix logic/visual issues mentioned. "
                "\n"
                "SPECIFIC INSTRUCTION FOR CHAOS FAILURES:\n"
                "- If the report mentions 'Latency' or 'Timeout', add retry logic (loops) or async handling.\n"
                "- If the report mentions 'Exception' (e.g., ConnectionError), wrap critical calls in `try...except` blocks and return a fallback value or log the error gracefully.\n"
                "- If the report mentions 'DataCorruption', add input validation (`isinstance`, `if x is None`).\n"
                "- GOAL: Increase the function's Survival Rate."
            )
            user_prompt = (
                f"MODULE: {module_name}\n"
                f"SPEC: {func_signature}\n\n"
                f"--- EXISTING CODE ---\n{existing_code}\n\n"
                f"--- BUG REPORT / ANALYSIS ---\n{feedback_report}\n\n"
                "Please rewrite the code to fix the issues:"
            )
        else:
            # --- CREATE MODE PROMPT (原有的) ---
            system_prompt = (
                "You are an expert Python Developer. "
                "Implement the specified function in Python. "
                "1. Output ONLY the code for this function. "
                "2. Handle edge cases. "
                "3. CRITICAL: If GUI involved, use 'tkinter' only."
            )
            user_prompt = (
                f"MODULE: {module_name}\n"
                f"Function Specification:\n{func_signature}\n\n"
                "Please write the full implementation code:"
            )

        # 5. 執行 LLM
        try:
            content_str, entropy = self.client.chat_complete_raw(model_name, system_prompt, user_prompt)
            code_body = self._extract_python_code(content_str)

            # 簡單補全 Import (僅在 Create 模式或 CodeBody 缺失時)
            if not feedback_report:
                if "import " not in code_body and ("List" in code_body or "Dict" in code_body):
                    code_body = "from typing import List, Dict, Any, Optional\n\n" + code_body

            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(code_body)

            return ImplementationResult(func_name, target_path, entropy, time.time() - start_time, True)

        except Exception as e:
            print(f"[!] Error implementing {func_name}: {e}")
            return ImplementationResult(func_name, target_path, -1.0, 0.0, False)

    # 這裡修改 generateFunctionCode 簽名以支援 feedback_report 字典
    def generateFunctionCode(
        self,
        spec_path: str,
        target_function_names: List[str],
        model_name: str= "gemma3:12b",
        max_workers: int = 2,
        feedback_map: Dict[str, str] = None  # [新增] Key: func_name, Value: report_string
    ) -> List[ImplementationResult]:

        if not os.path.exists(spec_path):
            raise FileNotFoundError(f"Spec file not found: {spec_path}")

        with open(spec_path, 'r', encoding='utf-8') as f:
            spec_data = json.load(f)

        module_dir = os.path.dirname(spec_path)
        results = []
        feedback_map = feedback_map or {}

        print(f"[*] Starting implementation/fix for {len(target_function_names)} functions...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {}
            for name in target_function_names:
                # 取得該函式對應的回饋報告 (如果有的話)
                report = feedback_map.get(name)
                future = executor.submit(
                    self._implement_single_function,
                    spec_data, name, module_dir, model_name, report
                )
                future_to_name[future] = name

            for future in as_completed(future_to_name):
                res = future.result()
                results.append(res)
                action = "Fixed" if feedback_map.get(res.function_name) else "Implemented"
                status = "Success" if res.success else "Failed"
                print(f"    [{action}] {res.function_name}: {status} (Entropy: {res.model_entropy})")

        return results
