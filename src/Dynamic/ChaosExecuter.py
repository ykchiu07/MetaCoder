import os
import json
import time
import random
import importlib.util
import unittest
import sys
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class ChaosResult:
    function_name: str
    injection_type: str
    survival_rate: float
    error_log: List[str]

class ChaosExecuter:
    def __init__(self, workspace_dir: str = "./vibe_workspace"):
        self.workspace_dir = os.path.abspath(workspace_dir)

    def _load_module_from_path(self, file_path: str, module_name: str):
        """動態載入模組"""
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module # 註冊到 sys.modules 以便被測試程式 import
            spec.loader.exec_module(module)
            return module
        return None

    def _create_poisoned_wrapper(self, original_func, injection_config: Dict):
        """
        [核心] 製造有毒的函式包裝器
        """
        def wrapper(*args, **kwargs):
            inj_type = injection_config.get('type')

            # 1. 延遲注入 (Latency)
            if inj_type == 'Latency':
                delay = float(injection_config.get('value', 1.0))
                # print(f"  [Chaos] Injecting Latency: {delay}s")
                time.sleep(delay)
                return original_func(*args, **kwargs)

            # 2. 異常注入 (Exception)
            elif inj_type == 'Exception':
                error_msg = injection_config.get('details', 'Chaos Injection Error')
                # print(f"  [Chaos] Injecting Exception: {error_msg}")
                # 模擬常見錯誤
                if "Timeout" in error_msg: raise TimeoutError(error_msg)
                if "Value" in error_msg: raise ValueError(error_msg)
                if "Connection" in error_msg: raise ConnectionError(error_msg)
                raise RuntimeError(f"Chaos: {error_msg}")

            # 3. 數據汙染 (Data Corruption)
            elif inj_type == 'DataCorruption':
                # 簡單將第一個字串參數變空，或數字變負數
                new_args = list(args)
                if new_args:
                    if isinstance(new_args[0], str): new_args[0] = ""
                    elif isinstance(new_args[0], (int, float)): new_args[0] = -99999
                # print(f"  [Chaos] Corrupting Data: {args} -> {new_args}")
                return original_func(*tuple(new_args), **kwargs)

            # 預設：不攻擊，直接執行
            return original_func(*args, **kwargs)

        return wrapper

    def produceChaos(self, module_name: str, test_rounds: int = 5) -> str:
        """
        執行混沌測試
        Returns: 報告 JSON 檔案路徑
        """
        module_dir = os.path.join(self.workspace_dir, module_name)
        plan_path = os.path.join(module_dir, "chaos_plan.json")
        tests_dir = os.path.join(module_dir, "tests")

        if not os.path.exists(plan_path):
            return f"Error: Plan not found at {plan_path}"

        print(f"[*] [ChaosExecuter] Unleashing chaos on {module_name}...")

        with open(plan_path, 'r') as f:
            plan = json.load(f)

        results = []

        # 遍歷計畫中的每個實驗
        for exp in plan.get('experiments', []):
            target_func_name = exp['target_function']
            injections = exp.get('injections', [])

            # 1. 尋找對應的實作檔案與測試檔案
            impl_file = "__init_logic__.py" if target_func_name == "__init__" else f"{target_func_name}.py"
            impl_path = os.path.join(module_dir, impl_file)
            test_path = os.path.join(tests_dir, f"test_{target_func_name}.py")

            if not os.path.exists(test_path):
                print(f"  [Skip] No unit test found for {target_func_name}. Cannot drive execution.")
                continue

            # 2. 載入目標模組 (為了 Patch)
            # 注意：這裡我們假設每個函式是獨立檔案，這讓 Patch 變得容易
            target_mod = self._load_module_from_path(impl_path, f"{module_name}.{target_func_name}")
            if not target_mod or not hasattr(target_mod, target_func_name):
                print(f"  [Skip] Implementation not found for {target_func_name}")
                continue

            # 保存原始函式
            original_func = getattr(target_mod, target_func_name)

            # 3. 針對每種注入類型進行測試
            for inj in injections:
                inj_type = inj['type']
                success_count = 0
                error_logs = []

                print(f"  > Target: {target_func_name} | Attack: {inj_type} | Rounds: {test_rounds}")

                # 套用「有毒」的包裝器
                poisoned_func = self._create_poisoned_wrapper(original_func, inj)
                setattr(target_mod, target_func_name, poisoned_func)

                # 4. 反覆執行測試
                for i in range(test_rounds):
                    # 使用 unittest TestLoader 來載入並執行該測試檔案
                    loader = unittest.TestLoader()
                    try:
                        # 動態載入測試模組
                        test_spec = importlib.util.spec_from_file_location("temp_test", test_path)
                        test_mod = importlib.util.module_from_spec(test_spec)
                        test_spec.loader.exec_module(test_mod)

                        suite = loader.loadTestsFromModule(test_mod)
                        runner = unittest.TextTestRunner(stream=open(os.devnull, 'w'), verbosity=0) # 靜音輸出
                        result = runner.run(suite)

                        if result.wasSuccessful():
                            success_count += 1
                        else:
                            # 測試失敗 (代表程式碼沒處理好這個異常)
                            err_msg = f"Round {i+1}: Test Failed."
                            if result.errors: err_msg += f" Err: {result.errors[0][1].splitlines()[-1]}"
                            if result.failures: err_msg += f" Fail: {result.failures[0][1].splitlines()[-1]}"
                            error_logs.append(err_msg)

                    except Exception as e:
                        error_logs.append(f"Round {i+1}: Crashed ({str(e)})")

                # 5. 復原原始函式 (清理戰場)
                setattr(target_mod, target_func_name, original_func)

                # 記錄結果
                survival_rate = round(success_count / test_rounds, 2)
                results.append({
                    "function": target_func_name,
                    "injection": inj_type,
                    "survival_rate": survival_rate,
                    "status": "RESILIENT" if survival_rate >= 0.8 else "FRAGILE",
                    "details": inj,
                    "logs": error_logs[:3] # 只留前幾條錯誤以免 JSON 太大
                })

                print(f"    -> Survival Rate: {survival_rate*100}%")

        # 6. 輸出報告
        report_path = os.path.join(module_dir, "chaos_report.json")
        final_output = {
            "timestamp": time.time(),
            "module": module_name,
            "results": results
        }
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=4)

        return report_path
