import unittest
import os
import sys
import importlib.util
from typing import Dict, Tuple

class TestRunner:
    def __init__(self, workspace_root: str):
        self.workspace_root = os.path.abspath(workspace_root)

    def run_module_tests(self, module_name: str) -> Dict[str, bool]:
        results = {}

        # [Fix 3] 確保專案根目錄在 sys.path 中，這樣測試檔案中的 import project.module 才能運作
        if self.workspace_root not in sys.path:
            sys.path.insert(0, self.workspace_root)

        # 假設結構: workspace/module_name/tests/test_xxx.py
        # 我們需要找的是專案下的那個資料夾
        mod_dir = os.path.join(self.workspace_root, module_name)
        tests_dir = os.path.join(mod_dir, "tests")

        # 嘗試另一種結構：如果 module_name 本身包含路徑
        if not os.path.exists(tests_dir):
             # 試著搜尋第一層子目錄
             for d in os.listdir(self.workspace_root):
                 if d == module_name:
                     tests_dir = os.path.join(self.workspace_root, d, "tests")
                     break

        if not os.path.exists(tests_dir):
            print(f"[TestRunner] Tests dir not found: {tests_dir}")
            return results

        print(f"[TestRunner] Scanning {tests_dir}...")

        for f in os.listdir(tests_dir):
            if f.startswith("test_") and f.endswith(".py"):
                func_name = f[5:-3] # remove 'test_' and '.py'
                test_path = os.path.join(tests_dir, f)

                try:
                    # 使用 unittest Discovery 比較穩健
                    # 但為了單檔執行，我們用 loader
                    loader = unittest.TestLoader()
                    # 這裡使用 discover 模式，讓它自己處理 import
                    suite = loader.discover(start_dir=tests_dir, pattern=f, top_level_dir=self.workspace_root)

                    with open(os.devnull, 'w') as null_stream:
                        runner = unittest.TextTestRunner(stream=null_stream, verbosity=0)
                        result = runner.run(suite)

                    passed = result.wasSuccessful()
                    results[func_name] = passed
                    # print(f"  > {func_name}: {'Pass' if passed else 'Fail'}")

                except Exception as e:
                    print(f"[TestRunner] Error running {f}: {e}")
                    results[func_name] = False

        return results
