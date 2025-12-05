import os
import json
import time
import re
from typing import List, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from OllamaClient import OllamaClient

@dataclass
class TestGenerationResult:
    function_name: str
    test_file_path: str
    model_entropy: float
    duration: float
    skipped: bool  # 是否因為沒有回傳值而跳過

class TestSpawner:
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.client = OllamaClient(ollama_url)

    def _extract_python_code(self, text: str) -> str:
        match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if match: return match.group(1)
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match: return match.group(1)
        return text

    def _should_generate_test(self, return_type: str) -> bool:
        """判斷是否需要生成單元測試 (有無回傳值)"""
        if not return_type: return False
        normalized = return_type.lower().strip()
        return normalized not in ['none', 'void', 'noreturn', 'nothing']

    def _generate_single_test(self, spec_data: Dict, func_name: str, tests_dir: str, model_name: str) -> TestGenerationResult:
        start_time = time.time()

        # 1. 獲取函式規格
        target_func_spec = next((f for f in spec_data.get('functions', []) if f['name'] == func_name), None)
        if not target_func_spec:
            return TestGenerationResult(func_name, "", -1.0, 0.0, True)

        # 2. 檢查回傳值
        return_type = target_func_spec.get('return_type', 'None')
        if not self._should_generate_test(return_type):
            print(f"    > Skipping test for {func_name} (Return type: {return_type})")
            return TestGenerationResult(func_name, "", 0.0, 0.0, True)

        print(f"    > Generating Unit Test for {func_name}...")

        # 3. 準備檔案路徑
        test_filename = f"test_{func_name}.py"
        test_file_path = os.path.join(tests_dir, test_filename)

        # 4. 準備 Prompt
        module_name = spec_data.get('module_name', 'unknown_module')

        system_prompt = (
            "You are a QA Engineer Expert in Python unittest. "
            "Write a comprehensive unit test for the specified function. "
            "1. Import `unittest`. "
            "2. Assume the function is available to import (e.g., `from ..{func_name} import {func_name}`). "
            "3. Cover at least 2-3 scenarios (normal case, edge case). "
            "4. Assert the return value matches expectation. "
            "5. Output ONLY the python code."
        )

        func_info = (
            f"Module: {module_name}\n"
            f"Function: {func_name}\n"
            f"Arguments: {target_func_spec.get('args')}\n"
            f"Return Type: {return_type}\n"
            f"Description: {target_func_spec.get('docstring')}"
        )

        user_prompt = (
            f"Target Function Info:\n{func_info}\n\n"
            "Generate the unittest code now:"
        )

        try:
            content_str, entropy = self.client.chat_complete_raw(model_name, system_prompt, user_prompt)
            code_body = self._extract_python_code(content_str)

            # 加入 sys.path hack 讓測試在碎片化狀態下也能跑 (可選，視您如何執行測試而定)
            # 這裡簡單加上標準 import 頭
            if "import unittest" not in code_body:
                code_body = "import unittest\n" + code_body

            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(code_body)

            return TestGenerationResult(func_name, test_file_path, entropy, time.time() - start_time, False)

        except Exception as e:
            print(f"[!] Error generating test for {func_name}: {e}")
            return TestGenerationResult(func_name, "", -1.0, 0.0, True)

    def generateUnitTest(self, spec_path: str, target_function_names: List[str], model_name: str) -> List[TestGenerationResult]:
        """
        批次生成單元測試
        """
        if not os.path.exists(spec_path):
            raise FileNotFoundError(f"Spec file not found: {spec_path}")

        with open(spec_path, 'r', encoding='utf-8') as f:
            spec_data = json.load(f)

        module_dir = os.path.dirname(spec_path)
        tests_dir = os.path.join(module_dir, "tests")
        if not os.path.exists(tests_dir):
            os.makedirs(tests_dir)

        results = []
        print(f"[*] Spawning tests for {len(target_function_names)} functions...")

        # 同樣支援並行生成
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_name = {
                executor.submit(self._generate_single_test, spec_data, name, tests_dir, model_name): name
                for name in target_function_names
            }

            for future in as_completed(future_to_name):
                res = future.result()
                results.append(res)
                if not res.skipped:
                    print(f"    [Test Created] {res.test_file_path} (Entropy: {res.model_entropy})")

        return results
