import os
import io

def export_project_content(root_dir=".", output_filename="project_content_export.txt"):
    """
    遍歷指定資料夾，將所有檔案內容匯出到單一文字檔案中。

    Args:
        root_dir (str): 專案的根目錄。
        output_filename (str): 輸出的文字檔案名稱。
    """
    # 指定要跳過的資料夾名稱
    EXCLUDE_DIRS = ['__pycache__', 'vibe_workspace']
    # 指定要跳過的隱藏資料夾（以 '.' 開頭）
    EXCLUDE_PREFIX = ('.',)

    print(f"正在從 '{root_dir}' 開始掃描專案...")

    # 使用 io.open 確保寫入時的編碼處理
    with io.open(output_filename, 'w', encoding='utf-8') as outfile:

        # 寫入檔頭，作為內容分隔
        outfile.write("=" * 80 + "\n")
        outfile.write(f"專案內容匯出報告 (根目錄: {os.path.abspath(root_dir)})\n")
        outfile.write("=" * 80 + "\n\n")

        # os.walk(top, topdown=True, onerror=None, followlinks=False)
        # topdown=True 允許我們在遍歷前修改 dirs
        for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):

            # --- 排除資料夾處理 ---

            # 遍歷 dirnames 的副本，以便在迭代時修改原始的 dirnames 列表
            # 這樣 os.walk 就不會進入這些資料夾
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(EXCLUDE_PREFIX)]

            # 檢查當前路徑是否在排除列表中，如果不是根目錄，且以排除前綴開頭，則跳過
            if dirpath != root_dir and os.path.basename(dirpath).startswith(EXCLUDE_PREFIX):
                continue

            # --- 檔案內容處理 ---

            # 過濾掉非 Python 檔案或你不想匯出的檔案（這裡只排除隱藏檔案）
            filenames = [f for f in filenames if not f.startswith(EXCLUDE_PREFIX)]

            for filename in filenames:
                file_path = os.path.join(dirpath, filename)

                # 忽略腳本本身
                if file_path == output_filename or file_path == os.path.basename(__file__):
                    continue

                try:
                    # 寫入檔案路徑作為分隔線
                    relative_path = os.path.relpath(file_path, root_dir)
                    outfile.write("\n" + "#" * 20 + f" 檔案: {relative_path} " + "#" * 20 + "\n")

                    # 讀取檔案內容
                    with io.open(file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                        content = infile.read()
                        outfile.write(content)

                    outfile.write("\n" + "#" * 70 + "\n") # 檔案內容結束分隔線

                except Exception as e:
                    # 處理讀取錯誤（例如二進位檔案或編碼問題）
                    outfile.write(f"\n[無法讀取檔案 {file_path}，錯誤: {e}]\n")
                    outfile.write("#" * 70 + "\n")

    print(f"\n✅ 匯出完成！內容已儲存至 '{output_filename}'。")
    print(f"現在你可以複製 '{output_filename}' 的內容貼給我了。")


if __name__ == "__main__":
    # 執行函數，預設掃描當前目錄
    export_project_content(root_dir=".")
