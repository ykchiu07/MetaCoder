import os
import json
import time
import re
from typing import List, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from OllamaClient import OllamaClient

import threading # 新增引用

@dataclass
class ImplementationResult:
    function_name: str
    file_path: str
    model_entropy: float
    duration: float
    success: bool
    version: int = 0  # [Fix] 補上這個漏掉的欄位

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

    def _get_dependency_context(self, module_dir: str, spec_data: Dict) -> str:
        try:
            project_dir = os.path.dirname(module_dir)
            arch_path = os.path.join(project_dir, "architecture.json")
            if not os.path.exists(arch_path): return ""

            with open(arch_path, 'r') as f: arch = json.load(f)

            # 判斷是否為 Main 模組
            current_mod_name = os.path.basename(module_dir)
            is_main = (current_mod_name == "main" or spec_data.get('module_name') == "main")

            dependencies = []
            if is_main:
                # [Fix 4] 如果是 Main，它依賴所有模組
                dependencies = [m['name'] for m in arch.get('modules', [])]
            else:
                target_mod_info = next((m for m in arch.get('modules', []) if m['name'] == current_mod_name), None)
                if target_mod_info:
                    dependencies = target_mod_info.get('dependencies', [])

            context = "EXTERNAL DEPENDENCIES (APIs you can use):\n"

            for dep_name in dependencies:
                # 忽略自己
                if dep_name == current_mod_name: continue

                dep_spec_path = os.path.join(project_dir, dep_name, "spec.json")
                if os.path.exists(dep_spec_path):
                    with open(dep_spec_path, 'r') as f:
                        dep_spec = json.load(f)
                        # 摘要 API
                        funcs = [f"{f['name']}(...)" for f in dep_spec.get('functions', [])]
                        desc = dep_spec.get('description', '')
                        context += f"- Module '{dep_name}': {desc}\n  Exports: {', '.join(funcs)}\n"

            return context
        except Exception as e:
            print(f"Error building context: {e}")
            return ""

    def _update_status_file(self, module_dir: str, func_name: str, status: str, entropy: float, version: int):
        """[修正] 紀錄詳細資訊到 .status.json"""
        status_path = os.path.join(module_dir, ".status.json")
        data = {}
        if os.path.exists(status_path):
            try:
                with open(status_path, 'r') as f: data = json.load(f)
            except: pass

        data[func_name] = {
            "status": status,
            "entropy": entropy,
            "version": version,
            "timestamp": time.time()
        }

        with open(status_path, 'w') as f:
            json.dump(data, f, indent=4)

    def _get_next_version(self, module_dir: str, func_name: str) -> int:
        status_path = os.path.join(module_dir, ".status.json")
        if os.path.exists(status_path):
            try:
                with open(status_path, 'r') as f:
                    data = json.load(f)
                    if func_name in data and isinstance(data[func_name], dict):
                        return data[func_name].get("version", 0) + 1
            except: pass
        return 1

    def _implement_single_function(self, spec_data: Dict, func_name: str, module_dir: str, model_name: str, feedback_report: str, cancel_event) -> ImplementationResult:
        start_time = time.time()
        filename = "__init_logic__.py" if func_name == "__init__" else f"{func_name}.py"
        target_path = os.path.join(module_dir, filename)

        # 1. 準備 Context
        target_func_spec = next((f for f in spec_data.get('functions', []) if f['name'] == func_name), None)
        module_name = spec_data.get('module_name', 'unknown')

        # [新增] 提取強制呼叫列表
        required_calls = target_func_spec.get('required_calls', [])
        calls_instruction = ""
        if required_calls:
            calls_instruction = f"CRITICAL REQUIREMENT: This function MUST call the following external APIs: {', '.join(required_calls)}."

        # [新增] 依賴注入
        dep_context = self._get_dependency_context(module_dir, spec_data)

        func_signature = (
            f"Function: {func_name}\n"
            f"Args: {target_func_spec.get('args')}\n"
            f"Return: {target_func_spec.get('return_type')}\n"
            f"Doc: {target_func_spec.get('docstring')}"
        )

        system_prompt = (
            "You are an expert Python Developer. Implement the function based on the spec.\n"
            "RULES:\n"
            "1. Use the provided EXTERNAL DEPENDENCIES to make correct import calls.\n"
            "2. Output ONLY Python code."
        )

        user_prompt = (
            f"MODULE: {module_name}\n"
            f"{dep_context}\n"
            f"TARGET SPEC:\n{func_signature}\n"
            f"{calls_instruction}\n\n" # [關鍵注入]
            "Implement this function."
        )

        if feedback_report: # Fix mode logic (省略，保持原樣但加入 dep_context)
             user_prompt = f"FIX REQUEST:\n{feedback_report}\n\n" + user_prompt

        # 2. 生成
        try:
            content_str, entropy = self.client.chat_complete_raw(model_name, system_prompt, user_prompt, cancel_event=cancel_event)
            code_body = self._extract_python_code(content_str)

            # 簡單修補 import (如果 LLM 沒寫)
            if "import" not in code_body:
                code_body = "from typing import Any, List, Dict, Optional\n" + code_body

            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(code_body)

            # 3. 更新狀態
            version = self._get_next_version(module_dir, func_name)
            self._update_status_file(module_dir, func_name, "implemented", entropy, version)

            return ImplementationResult(func_name, target_path, entropy, time.time() - start_time, True, version)

        except InterruptedError:
            return ImplementationResult(func_name, target_path, 0.0, 0.0, False)
        except Exception as e:
            print(f"Error: {e}")
            return ImplementationResult(func_name, target_path, -1.0, 0.0, False)

    # 這裡修改 generateFunctionCode 簽名以支援 feedback_report 字典
    def generateFunctionCode(
        self,
        spec_path: str,
        target_function_names: List[str],
        model_name: str= "gemma3:12b",
        max_workers: int = 3,
        feedback_map: Dict[str, str] = None,  # [新增] Key: func_name, Value: report_string
        cancel_event: threading.Event = None  # [新增] 接收取消旗標
    ) -> List[ImplementationResult]:

        if not os.path.exists(spec_path):
            raise FileNotFoundError(f"Spec file not found: {spec_path}")

        with open(spec_path, 'r', encoding='utf-8') as f:
            spec_data = json.load(f)

        module_dir = os.path.dirname(spec_path)
        results = []
        feedback_map = feedback_map or {}

        print(f"[*] Starting implementation for {len(target_function_names)} functions with {max_workers} workers...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {}
            for name in target_function_names:
                if cancel_event and cancel_event.is_set():
                    break
                report = feedback_map.get(name)
                # [關鍵] 將 cancel_event 傳入 _implement_single_function
                future = executor.submit(
                    self._implement_single_function,
                    spec_data, name, module_dir, model_name, report, cancel_event
                )
                future_to_name[future] = name

            for future in as_completed(future_to_name):
                # 這裡不 break，讓正在跑的任務有機會完成或拋出 InterruptedError
                try:
                    res = future.result()
                    results.append(res)
                except InterruptedError:
                    print(f"   [Stopped] {future_to_name[future]}")
                except Exception as e:
                    print(f"   [Error] {future_to_name[future]}: {e}")
                action = "Fixed" if feedback_map.get(res.function_name) else "Implemented"
                status = "Success" if res.success else "Failed"
                print(f"    [{action}] {res.function_name}: {status} (Entropy: {res.model_entropy})")

        return results

    def implement_function_direct(self, spec_path: str, func_name: str, model_name: str, cancel_event=None) -> ImplementationResult:
            with open(spec_path, 'r') as f: spec_data = json.load(f)
            module_dir = os.path.dirname(spec_path)
            return self._implement_single_function(spec_data, func_name, module_dir, model_name, None, cancel_event)
