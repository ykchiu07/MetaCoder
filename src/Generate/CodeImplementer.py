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

    def _implement_single_function(self, spec_data: Dict, func_name: str, module_dir: str, model_name: str) -> ImplementationResult:
        """(內部方法) 實作單一函式"""
        start_time = time.time()

        # 1. 推導檔案路徑
        filename = "__init_logic__.py" if func_name == "__init__" else f"{func_name}.py"
        target_path = os.path.join(module_dir, filename)

        # 2. 獲取函式規格
        target_func_spec = next((f for f in spec_data.get('functions', []) if f['name'] == func_name), None)
        if not target_func_spec:
            print(f"[!] Spec not found for function: {func_name}")
            return ImplementationResult(func_name, target_path, -1.0, 0.0, False)

        print(f"    > Implementing {func_name} with {model_name}...")

        # 3. 準備 Prompt
        module_name = spec_data.get('module_name', 'unknown_module')
        class_name = spec_data.get('class_name', None)
        context_str = f"Module: {module_name}\nClass: {class_name}" if class_name else f"Module: {module_name}"

        func_signature = (
            f"Name: {target_func_spec['name']}\n"
            f"Args: {target_func_spec.get('args')}\n"
            f"Return: {target_func_spec.get('return_type')}\n"
            f"Description: {target_func_spec.get('docstring')}"
        )

        system_prompt = (
            "You are an expert Python Developer. "
            "Implement the specified function in Python. "
            "1. Output ONLY the code for this function (including necessary imports). "
            "2. Handle edge cases and potential errors. "
            "3. Do NOT output a Class definition, just the method body/function. "
            "4. Respect the arguments provided in the specification."
            "5. If the function involves Graphical User Interface (GUI), YOU MUST USE 'tkinter'.\n"
            "   - Do NOT use PyQt, PySide, Kivy, or wxPython.\n"
            "   - The system's runtime analysis tools are hooked into tkinter only.\n"
            "   - Using other GUI libraries will cause the build to fail."
        )

        user_prompt = (
            f"{context_str}\n"
            f"Function Specification:\n{func_signature}\n\n"
            "Please write the full implementation code:"
        )

        try:
            content_str, entropy = self.client.chat_complete_raw(model_name, system_prompt, user_prompt)
            code_body = self._extract_python_code(content_str)

            # 簡單補全 Import
            final_code = code_body
            if "import " not in code_body and ("List" in code_body or "Dict" in code_body):
                final_code = "from typing import List, Dict, Any, Optional\n\n" + code_body

            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(final_code)

            return ImplementationResult(func_name, target_path, entropy, time.time() - start_time, True)

        except Exception as e:
            print(f"[!] Error implementing {func_name}: {e}")
            return ImplementationResult(func_name, target_path, -1.0, 0.0, False)

    def generateFunctionCode(self, spec_path: str, target_function_names: List[str], model_name: str, max_workers: int = 2) -> List[ImplementationResult]:
        """
        批次實作函式
        Args:
            spec_path: spec.json 的路徑
            target_function_names: 要實作的函式名稱列表 (例如 ['login', 'logout'])
            model_name: 使用的模型名稱
            max_workers: 並行執行緒數 (建議配合 OLLAMA_NUM_PARALLEL 使用)
        """
        if not os.path.exists(spec_path):
            raise FileNotFoundError(f"Spec file not found: {spec_path}")

        with open(spec_path, 'r', encoding='utf-8') as f:
            spec_data = json.load(f)

        module_dir = os.path.dirname(spec_path)
        results = []

        print(f"[*] Starting implementation for {len(target_function_names)} functions...")

        # 使用 ThreadPoolExecutor 進行並行處理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_name = {
                executor.submit(self._implement_single_function, spec_data, name, module_dir, model_name): name
                for name in target_function_names
            }

            for future in as_completed(future_to_name):
                res = future.result()
                results.append(res)
                status = "Success" if res.success else "Failed"
                print(f"    [Done] {res.function_name}: {status} (Entropy: {res.model_entropy})")

        return results
