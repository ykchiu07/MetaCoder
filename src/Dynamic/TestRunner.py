import unittest
import os
import sys
import importlib.util
from typing import Dict, Tuple

class TestRunner:
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    def run_function_test(self, module_name: str, func_name: str) -> Tuple[bool, str]:
        """
        執行特定函式的單元測試
        回傳: (是否通過, 訊息)
        """
        # 推斷測試檔案路徑
        # 假設結構: workspace/module/tests/test_func.py
        test_path = os.path.join(self.workspace_root, module_name, "tests", f"test_{func_name}.py")

        if not os.path.exists(test_path):
            return False, "No test file found"

        try:
            # 動態載入測試模組
            spec = importlib.util.spec_from_file_location(f"test_{func_name}", test_path)
            test_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(test_mod)

            # 載入並執行測試
            suite = unittest.TestLoader().loadTestsFromModule(test_mod)

            # 使用自訂的 Stream 避免汙染 Console，或者導入到 Log
            with open(os.devnull, 'w') as null_stream:
                runner = unittest.TextTestRunner(stream=null_stream, verbosity=0)
                result = runner.run(suite)

            if result.wasSuccessful():
                return True, "Pass"
            else:
                return False, f"Fail: {len(result.failures)} failures, {len(result.errors)} errors"

        except Exception as e:
            return False, f"Error: {str(e)}"

    def run_module_tests(self, module_name: str) -> Dict[str, bool]:
        """
        執行該模組下所有已知的測試
        回傳: { 'func_name': True/False }
        """
        results = {}
        tests_dir = os.path.join(self.workspace_root, module_name, "tests")
        if not os.path.exists(tests_dir):
            return results

        for f in os.listdir(tests_dir):
            if f.startswith("test_") and f.endswith(".py"):
                func_name = f[5:-3] # remove test_ and .py
                passed, _ = self.run_function_test(module_name, func_name)
                results[func_name] = passed
        return results
