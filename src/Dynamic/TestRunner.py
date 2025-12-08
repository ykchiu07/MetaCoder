import unittest
import os
import sys
from typing import Dict

class TestRunner:
    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)

    def run_module_tests(self, module_name: str) -> Dict[str, bool]:
        results = {}

        # 1. 確保 Import 路徑正確
        if self.workspace_root not in sys.path:
            sys.path.insert(0, self.workspace_root)

        # 2. 尋找測試目錄
        # 支援兩種結構:
        # A. root/module/tests/
        # B. root/module/ (tests inside)
        target_dir = os.path.join(self.workspace_root, module_name, "tests")
        if not os.path.exists(target_dir):
            # Fallback: check if module itself has tests
            target_dir = os.path.join(self.workspace_root, module_name)

        if not os.path.exists(target_dir):
            print(f"[TestRunner] No test directory found for {module_name}")
            return {}

        print(f"[TestRunner] Discovering tests in {target_dir}...")

        try:
            # 3. 使用 Discover 掃描所有測試
            loader = unittest.TestLoader()
            suite = loader.discover(start_dir=target_dir, pattern="test_*.py", top_level_dir=self.workspace_root)

            # 4. 執行
            # 使用自訂 result 來收集每個 case 的結果
            runner = unittest.TextTestRunner(verbosity=0)
            result = runner.run(suite)

            # 5. 解析結果
            # 預設 result 物件沒有直接提供 {func: bool} 的 map，我們需要自己拼湊
            # 這裡簡單處理：如果有失敗，標記為 False。
            # 但使用者想看到「每個函式」的狀態。
            # 由於 unittest 是以 Class/Method 為單位，我們嘗試解析 test id
            # id 格式通常是: module.class.method

            # 為了拿到所有跑過的 test，我們需要一個 set
            all_tests = set()
            def collect_tests(suite_obj):
                if hasattr(suite_obj, '__iter__'):
                    for x in suite_obj: collect_tests(x)
                else:
                    all_tests.add(suite_obj)
            collect_tests(suite)

            failed_ids = {f[0].id() for f in result.failures + result.errors}

            for test_case in all_tests:
                test_id = test_case.id()
                # test_id e.g., "vibe_workspace.auth.tests.test_login.TestLogin.test_login_success"
                # 我們嘗試提取 function name (假設測試檔名對應函式名)
                # 假設 test_login.py 對應 login 函式
                parts = test_id.split('.')
                func_name = "unknown"
                for p in parts:
                    if p.startswith("test_") and p != "test_": # 找到 test_login
                        func_name = p[5:] # remove test_
                        break

                # 判斷結果
                is_pass = test_id not in failed_ids

                # 存入 results (如果同一個函式有多個測試，只要有一個失敗就算失敗 AND logic)
                if func_name not in results:
                    results[func_name] = is_pass
                else:
                    results[func_name] = results[func_name] and is_pass

        except Exception as e:
            print(f"[TestRunner] Error: {e}")

        return results
