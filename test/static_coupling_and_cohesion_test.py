import os
import shutil
import tempfile
import textwrap
import math

# 嘗試匯入分析器
try:
    import sys
    sys.path.append("../src/Static")
    import StructureAnalyzer
except ImportError:
    print("錯誤：找不到 StructureAnalyzer，請確保檔案在同一目錄下。")
    exit()

def run_comparison_test():
    print("=== 架構品質光譜測試：天堂與地獄 ===\n")

    test_dir = tempfile.mkdtemp(prefix="arch_compare_")

    try:
        # =========================================================
        # 0. 準備環境：製造一些「被依賴」的雜訊模組
        # =========================================================
        # 為了讓惡性案例的耦合度飆高，我們需要製造一些它依賴的對象
        for name in ['db_driver', 'ui_widget', 'network_api', 'legacy_utils']:
            with open(os.path.join(test_dir, f"{name}.py"), "w") as f:
                f.write("# Dummy module")

        # =========================================================
        # 1. 惡性案例：God Object (高耦合 / 低內聚)
        # =========================================================
        # 特徵：
        # - Import 了 4 個模組 (耦合高 -> 分數低)
        # - 類別 GodManager 做了三件不相干的事 (User, Config, Log)
        # - User 用 self.db, Config 用 self.cfg, Log 用 self.file
        # - 預期 LCOM4 = 3 (分裂成三個區塊)，Density = 0.0 (完全無交集)
        code_bad = textwrap.dedent("""
            import db_driver
            import ui_widget
            import network_api
            import legacy_utils

            class GodManager:
                def __init__(self):
                    self.db_conn = "db://..."
                    self.cfg = {}
                    self.log_file = "app.log"

                # --- 職責 A: 處理資料庫 (只用 db_conn) ---
                def fetch_user(self, uid):
                    # 假裝使用了 db_driver
                    return self.db_conn + str(uid)

                def save_user(self, uid, data):
                    print(self.db_conn, data)

                # --- 職責 B: 處理設定 (只用 cfg) ---
                def load_config(self):
                    self.cfg['theme'] = 'dark'

                def get_theme(self):
                    return self.cfg.get('theme')

                # --- 職責 C: 處理日誌 (只用 log_file) ---
                def write_log(self, msg):
                    print(f"Writing to {self.log_file}: {msg}")
        """)
        with open(os.path.join(test_dir, "bad_god_object.py"), "w", encoding="utf-8") as f:
            f.write(code_bad)

        # =========================================================
        # 2. 理想案例：Pure Component (低耦合 / 高內聚)
        # =========================================================
        # 特徵：
        # - 零 Import (耦合低 -> 分數 100)
        # - 類別 MovingAverage 專注計算
        # - 所有方法都圍繞著 self.window 和 self.values 運作
        # - 預期 LCOM4 = 1，Density ≈ 1.0 (強內聚)
        code_good = textwrap.dedent("""
            class MovingAverage:
                def __init__(self, size):
                    self.window_size = size
                    self.values = []
                    self.sum = 0.0

                def add(self, val):
                    # 使用了 values, sum, window_size
                    self.values.append(val)
                    self.sum += val
                    if len(self.values) > self.window_size:
                        removed = self.values.pop(0)
                        self.sum -= removed

                def get_average(self):
                    # 使用了 values, sum
                    if not self.values:
                        return 0.0
                    return self.sum / len(self.values)

                def reset(self):
                    # 使用了 values, sum
                    self.values = []
                    self.sum = 0.0
        """)
        with open(os.path.join(test_dir, "good_component.py"), "w", encoding="utf-8") as f:
            f.write(code_good)

        # =========================================================
        # 3. 執行分析
        # =========================================================
        analyzer = StructureAnalyzer.StructureAnalyzer(test_dir)

        # 格式化輸出
        headers = ["Module", "Coupling(Score)", "LCOM4", "Density", "評價"]
        row_fmt = "{:<20} | {:<15} | {:<6} | {:<8} | {}"

        print(row_fmt.format(*headers))
        print("-" * 90)

        for mod in ["bad_god_object", "good_component"]:
            coup = analyzer.calculateCoupling(mod)
            cohesion = analyzer.calculateCohesion(mod)

            # 取出第一個類別的資料來展示
            cls_name = list(cohesion.keys())[0]
            lcom = cohesion[cls_name]['lcom4']
            dens = cohesion[cls_name]['density']

            comment = ""
            if coup > 80 and lcom == 1 and dens > 0.8:
                comment = "✅ 完美架構 (高內聚低耦合)"
            elif coup < 60 and (lcom > 1 or dens < 0.3):
                comment = "❌ 惡性架構 (低內聚高耦合)"
            else:
                comment = "⚠️ 普通"

            print(row_fmt.format(
                mod,
                f"{coup:.1f}",
                str(lcom),
                f"{dens:.2f}",
                comment
            ))

            # 額外顯示 Import 數量驗證耦合計算
            if mod == "bad_god_object":
                imports = len(analyzer.dependencies[mod])
                expected_score = 100 * math.exp(-0.2 * imports)
                print(f"   (Imports: {imports}, Expected Score: {expected_score:.1f})")

    finally:
        shutil.rmtree(test_dir)
        print("\n[*] 測試結束，已清理環境。")

if __name__ == "__main__":
    run_comparison_test()
