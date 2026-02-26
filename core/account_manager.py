import os

class AccountManager:
    def __init__(self, base_dir="./browser_session"):
        self.base_dir = os.path.abspath(base_dir)
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)

    def get_accounts(self):
        """获取所有已存在的账号目录列表"""
        return [d for d in os.listdir(self.base_dir) if os.path.isdir(os.path.join(self.base_dir, d))]

    def get_session_path(self, account_name):
        """获取特定账号的 Session 路径"""
        path = os.path.join(self.base_dir, account_name)
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def create_account(self, account_name):
        """创建一个新账号的目录"""
        path = os.path.join(self.base_dir, account_name)
        if not os.path.exists(path):
            os.makedirs(path)
        return path
