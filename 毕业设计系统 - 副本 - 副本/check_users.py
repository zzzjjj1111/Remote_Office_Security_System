import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from core.db import db, User
from app import create_app

def check_users():
    app = create_app()
    with app.app_context():
        users = User.query.all()
        print(f'Found {len(users)} users')
        
        for i, user in enumerate(users[:10]):  # 只显示前10个用户
            print(f'User {i+1}:')
            print(f'  ID: {user.id}')
            print(f'  Name: {repr(user.name)}')
            print(f'  Name (encoded): {user.name.encode("utf-8") if user.name else None}')
            print(f'  WorkWechatID: {user.work_wechat_id}')
            print(f'  Trust Score: {user.trust_score}')
            print()

if __name__ == '__main__':
    check_users()