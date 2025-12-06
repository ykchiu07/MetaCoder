import os
import datetime
from typing import List, Dict, Optional
import git # pip install gitpython

class VersionController:
    def __init__(self, workspace_dir: str = "./vibe_workspace"):
        self.workspace_dir = os.path.abspath(workspace_dir)
        if not os.path.exists(self.workspace_dir):
            os.makedirs(self.workspace_dir)

        # 初始化 Git 儲存庫
        try:
            self.repo = git.Repo(self.workspace_dir)
        except git.exc.InvalidGitRepositoryError:
            print(f"[*] Initializing new Git repo in {self.workspace_dir}")
            self.repo = git.Repo.init(self.workspace_dir)
            self._setup_gitignore()

    def _setup_gitignore(self):
        """建立 .gitignore 防止追蹤不必要的檔案"""
        gitignore_path = os.path.join(self.workspace_dir, ".gitignore")
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, "w") as f:
                f.write("__pycache__/\n*.pyc\n.env\n.DS_Store\n")
            self.repo.index.add([gitignore_path])
            self.repo.index.commit("Initial commit: Add .gitignore")

    def archiveVersion(self, message: str) -> str:
        """
        [歸檔] 將目前的專案狀態提交 (Commit)
        Args:
            message: 提交訊息 (例如 "Initial structure for Auth module")
        Returns:
            commit_hash (short sha)
        """
        # 1. 加入所有變更 (git add .)
        # untracked_files 處理新增檔案，diff(None) 處理修改檔案
        if self.repo.is_dirty(untracked_files=True):
            self.repo.git.add(A=True) # A=True 相當於 add .

            # 2. 提交
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            full_msg = f"[{timestamp}] {message}"
            commit = self.repo.index.commit(full_msg)

            print(f"[VersionController] Archived: {full_msg} (Hash: {commit.hexsha[:7]})")
            return commit.hexsha
        else:
            print("[VersionController] No changes to archive.")
            return self.repo.head.commit.hexsha

    def rollbackVersion(self, commit_hash: str, file_path: str = None) -> bool:
        """
        [回滾] 將專案或特定檔案回復到指定版本
        Args:
            commit_hash: 目標版本的雜湊值
            file_path: 指定檔案路徑 (若為 None 則回滾整個專案)
        """
        try:
            if file_path:
                # 回滾單一檔案：git checkout <commit> -- <path>
                # 需要將絕對路徑轉換為相對於 repo 的路徑
                rel_path = os.path.relpath(file_path, self.workspace_dir)
                self.repo.git.checkout(commit_hash, "--", rel_path)
                print(f"[VersionController] Rolled back file '{rel_path}' to {commit_hash[:7]}")
            else:
                # 回滾整個專案：git reset --hard <commit>
                # 注意：這會丟棄所有未提交的變更，請確保 rollback 前有 archive
                self.repo.git.reset("--hard", commit_hash)
                print(f"[VersionController] Rolled back PROJECT to {commit_hash[:7]}")
            return True
        except Exception as e:
            print(f"[!] Rollback failed: {e}")
            return False

    def getHistory(self, limit: int = 10) -> List[Dict]:
        """獲取最近的提交紀錄供 GUI 顯示"""
        history = []
        for commit in list(self.repo.iter_commits(max_count=limit)):
            history.append({
                "hash": commit.hexsha,
                "short_hash": commit.hexsha[:7],
                "message": commit.message.strip(),
                "date": datetime.datetime.fromtimestamp(commit.committed_date).strftime("%Y-%m-%d %H:%M:%S")
            })
        return history
