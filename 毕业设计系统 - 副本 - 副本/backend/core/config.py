import os

class Config:
    # 基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'zero-trust-office-super-secret-key')
    
    # 数据库配置 (使用 PyMySQL)
    # 此处默认用 root 用户，密码为空或 root，请根据本地环境修改
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'mysql+pymysql://root:root@127.0.0.1/remote_office_protection_empty')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 企业微信配置（请替换为你的测试企业微信参数）
    WECHAT_CORP_ID = "ww48838ba8dca86723"  # 企业ID
    WECHAT_AGENT_ID = 1000002  # 应用AgentId
    WECHAT_SECRET = "5BS4jCReDrV_rHl1ZHS2jJJxlePCc6_CcBbxp7nt-nw"  # 应用Secret
    # ⚠️ 使用 cpolar 时，将 abc123.cpolar.cn 替换为实际的 cpolar HTTP 域名
    WECHAT_REDIRECT_URI = "http://31e8de14.r22.cpolar.top/login/callback"  # 回调地址
        
    # 前端回调地址
    FRONTEND_REDIRECT_URL = "http://31e8de14.r22.cpolar.top/login/callback"
    
    # 【新增】管理员白名单配置（这些用户访问OA时不需要启动Agent）
    # 可以配置职位列表或用户ID列表
    ADMIN_WHITELIST_POSITIONS = ['系统管理员', '安全管理员', '超级管理员']  # 职位白名单
    ADMIN_WHITELIST_USER_IDS = [1,]  # 用户ID白名单（可选，方便测试）
