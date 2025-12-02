import os
import json
import time
import re
from typing import List, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from OllamaClient import OllamaClient

@dataclass
class ImplementationResult:
    file_path: str
    model_entropy: float
    duration: float
    success: bool

class CodeImplementer:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.client = OllamaClient(ollama_url)

    def _extract_python_code(self, text: str) -> str:
        # 優先匹配 ```python
        match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if match: return match.group(1)
        # 其次匹配 ```
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match: return match.group(1)
        return text

    def generateFunctionCode(self, spec_path: str, target_fragment_path: str, model_name: str) -> ImplementationResult:
        """實作單一函式"""
        start_time = time.time()

        if not os.path.exists(spec_path):
            return ImplementationResult(target_fragment_path, -1.0, 0.0, False)

        with open(spec_path, 'r', encoding='utf-8') as f:
            spec_data = json.load(f)

        func_name = os.path.splitext(os.path.basename(target_fragment_path))[0]
        if func_name == "__init_logic__": func_name = "__init__"

        target_func_spec = next((f for f in spec_data.get('functions', []) if f['name'] == func_name), None)
        if not target_func_spec:
            return ImplementationResult(target_fragment_path, -1.0, 0.0, False)

        print(f"    > Implementing {func_name} with {model_name}...")

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
        )

        user_prompt = (
            f"{context_str}\n"
            f"Function Specification:\n{func_signature}\n\n"
            "Please write the full implementation code:"
        )

        try:
            content_str, entropy = self.client.chat_complete_raw(model_name, system_prompt, user_prompt)
            code_body = self._extract_python_code(content_str)

            # 簡單補全 Import，避免語法檢查報錯
            final_code = code_body
            if "import " not in code_body and ("List" in code_body or "Dict" in code_body):
                final_code = "from typing import List, Dict, Any, Optional\n\n" + code_body

            with open(target_fragment_path, 'w', encoding='utf-8') as f:
                f.write(final_code)

            return ImplementationResult(target_fragment_path, entropy, time.time() - start_time, True)

        except Exception as e:
            print(f"[!] Error implementing {func_name}: {e}")
            return ImplementationResult(target_fragment_path, -1.0, 0.0, False)

def implement_module_functions_parallel(spec_path: str, fragment_paths: List[str], model_name: str, max_workers: int = 2) -> List[ImplementationResult]:
    """雙執行緒並行實作"""
    implementer = CodeImplementer()
    results = []
    print(f"[*] Starting parallel implementation with {max_workers} threads...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {
            executor.submit(implementer.generateFunctionCode, spec_path, path, model_name): path
            for path in fragment_paths
        }

        for future in as_completed(future_to_path):
            res = future.result()
            results.append(res)
            status = "Success" if res.success else "Failed"
            print(f"    [Thread Done] {os.path.basename(res.file_path)}: {status}")

    return results
