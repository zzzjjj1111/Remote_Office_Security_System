from flask import Blueprint, current_app, request, jsonify, redirect
from core.db import db, User
from services.audit_service import audit_logger  # 【新增】导入审计日志服务
import requests
from core.config import Config
import jwt as jwt_lib
from datetime import datetime, timedelta


auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    模拟账号密码登录（为毕设演示新增的接口）
    """
    try:
        data = request.json or {}
        username = data.get('username', '')
        password = data.get('password', '')

        if not username or not password:
            return jsonify({"status": "error", "message": "用户名和密码不能为空"}), 400

        if password != "password123":
            try:
                audit_logger.log_auth(user_id=None, action='login_failed', status='failure',
                                      description=f'用户 {username} 登录失败：密码错误', error_message='密码错误')
            except Exception as audit_err:
                print(f"⚠️ 审计日志记录失败（已安全降级）: {audit_err}")
            return jsonify({"status": "error", "message": "账户信息或密码错误"}), 401

        # 【修复】全面支持 ID 与 work_wechat_id 登录
        user = User.query.filter_by(work_wechat_id=username).first()
        if not user and username.isdigit():
            user = User.query.filter_by(id=int(username)).first()
        
        if not user:
            return jsonify({"status": "error", "message": "用户不存在，请检查账号或 ID 是否正确"}), 404

        # 【新增】检查用户是否被管理员阻断
        if user.status == 'blocked':
            try:
                audit_logger.log_auth(user_id=user.id, action='login_blocked', status='failure',
                                      description=f'用户 {user.name} 尝试登录但已被阻断')
            except Exception as audit_err:
                print(f"⚠️ 审计日志记录失败（已安全降级）: {audit_err}")
            
            return jsonify({
                "status": "error",
                "code": "USER_BLOCKED",
                "message": f"您的账号已被管理员阻断，无法登录系统。请联系管理员解除阻断。",
                "data": {
                    "blocked_at": None,  # 可以从Alert表查询阻断时间
                    "contact": "请联系IT支持部门：ext. 8888"
                }
            }), 403

        # 【修复】安全地打印登录成功信息，避免Windows控制台编码问题
        try:
            import sys
            if sys.platform == 'win32':
                # Windows 环境下只打印 ASCII 字符，避免编码问题
                print(f" [Login] Login successful for user ID:{user.id}, Trust:{user.trust_score}")
            else:
                print(f" [Login] Login successful: {user.name} (ID:{user.id}, Trust:{user.trust_score})")
        except Exception as e:
            # 任何异常情况下都使用最安全的输出方式
            print(f" [Login] User {user.id} logged in successfully")

        # 【修复】生成JWT token，与OA系统兼容 (增加异常降级)
        try:
            system_token = jwt_lib.encode({
                'user_id': user.id,
                'username': user.name,
                'work_wechat_id': user.work_wechat_id,
                'exp': datetime.utcnow() + timedelta(days=7)
            }, 'your-secret-key', algorithm='HS256')
        except Exception as jwt_err:
            print(f" JWT generation failed, using fallback token: {jwt_err}")
            system_token = f"token_{user.id}_{user.work_wechat_id}"

        # 【核心修复】隔离审计日志，防止 Windows 底层 OSError 导致 500
        try:
            audit_logger.log_auth(
                user_id=user.id,
                action='login',
                status='success',
                description=f'User {user.id} login success'
            )
        except Exception as audit_err:
            print(f" Audit log failed (safe fallback): {audit_err}")

        return jsonify({
            "status": "success",
            "message": "Login successful",
            "access_token": system_token,
            "data": {
                "token": system_token,
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "position": user.position,
                    "trust_score": user.trust_score
                }
            }
        })
    except Exception as e:
        import traceback
        print("\n [Login API Critical Error] ")
        traceback.print_exc()
        print(f"Error details: {str(e)}\n")
        return jsonify({"status": "error", "message": f"Server internal error: {str(e)}"}), 500

@auth_bp.route('/get_login_url', methods=['GET'])
def get_login_url():
    corp_id = current_app.config.get('WORK_WECHAT_CORP_ID', 'test')
    agent_id = current_app.config.get('WORK_WECHAT_AGENT_ID', 'test')
    redirect_uri = current_app.config.get('FRONTEND_REDIRECT_URL', 'http://localhost:5173')
    login_url = f"https://open.work.weixin.qq.com/wwopen/sso/qrConnect?appid={corp_id}&agentid={agent_id}&redirect_uri={redirect_uri}&state=STATE"
    return jsonify({"status": "success", "login_url": login_url})

@auth_bp.route('/callback', methods=['GET', 'POST'])
def callback():
    code = request.args.get('code') or (request.json.get('code') if request.json else None)
    if not code:
        return jsonify({"status": "error", "message": "Missing code"}), 400
    
    work_wechat_id = "mock_admin_001"
    name = "演示管理员"
    department = "安全研发部"
    position = "研发工程师"
    
    user = User.query.filter_by(work_wechat_id=work_wechat_id).first()
    if not user:
        user = User(
            work_wechat_id=work_wechat_id,
            name=name,
            department=department,
            position=position,
            status='active',
            trust_score=100.0
        )
        db.session.add(user)
        db.session.commit()

    system_token = f"token_{user.id}_{user.work_wechat_id}"
    return jsonify({
        "status": "success",
        "data": {"token": system_token, "user": {"id": user.id}}
    })

@auth_bp.route('/me', methods=['GET'])
def get_me():
    token = request.headers.get('Authorization', '')
    if not token or not token.startswith('Bearer '):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        # 【修复】支持JWT token解析
        real_token = token.split(' ')[1]
        import jwt as jwt_lib
        payload = jwt_lib.decode(real_token, 'your-secret-key', algorithms=['HS256'])
        user_id = payload['user_id']
        user = User.query.get(user_id)
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404
        
        # 【调试】打印信任分，确认从数据库读取的值（避免中文）
        print(f" /api/auth/me - User ID:{user_id}, Trust score:{user.trust_score}")
        
        return jsonify({
            "status": "success",
            "data": {
                "id": user.id,
                "name": user.name,
                "department": user.department,
                "position": user.position,
                "trust_score": user.trust_score
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@auth_bp.route('/wechat/qrcode', methods=['GET'])
def get_wechat_qrcode():
    """生成企业微信授权链接（极简版）"""
    auth_url = f"https://open.work.weixin.qq.com/wwopen/sso/qrConnect?appid={Config.WECHAT_CORP_ID}&agentid={Config.WECHAT_AGENT_ID}&redirect_uri={Config.WECHAT_REDIRECT_URI}&state=STATE"
    return jsonify({"status": "success", "auth_url": auth_url})

@auth_bp.route('/wechat/callback', methods=['POST'])
def wechat_callback():
    """处理企业微信回调：code换用户信息 + 登录"""
    code = request.json.get('code')
    if not code:
        return jsonify({"status": "error", "message": "缺失code"}), 400

    try:
        # 1. 用code获取access_token
        token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={Config.WECHAT_CORP_ID}&corpsecret={Config.WECHAT_SECRET}"
        token_res = requests.get(token_url, timeout=10).json()
        if token_res.get('errcode') != 0:
            return jsonify({"status": "error", "message": "获取access_token失败"}), 400
        access_token = token_res['access_token']

        # 2. 用code获取用户userId
        user_url = f"https://qyapi.weixin.qq.com/cgi-bin/auth/getuserinfo?access_token={access_token}&code={code}"
        user_res = requests.get(user_url, timeout=10).json()
        if user_res.get('errcode') != 0:
            return jsonify({"status": "error", "message": "获取用户信息失败"}), 400
        user_id = user_res['UserId']

        # 3. 获取用户详细信息
        detail_url = f"https://qyapi.weixin.qq.com/cgi-bin/user/get?access_token={access_token}&userid={user_id}"
        detail_res = requests.get(detail_url, timeout=10).json()
        if detail_res.get('errcode') != 0:
            return jsonify({"status": "error", "message": "获取用户详情失败"}), 400
        user_name = detail_res.get('name', '未知用户')

        # 4. 同步/创建用户到数据库（极简版）
        user = User.query.filter_by(wechat_userid=user_id).first()
        if not user:
            user = User(
                wechat_userid=user_id,
                name=user_name,  # 修复：使用 name 而非 username
                trust_score=100,  # 初始信任分100
                created_at=datetime.now()
            )
            db.session.add(user)
            db.session.commit()

        # 5. 生成本系统token（复用现有JWT逻辑）
        token = jwt_lib.encode({
            'user_id': user.id,
            'username': user.name,  # 修复：使用 name
            'exp': datetime.utcnow() + timedelta(days=7)
        }, 'your-secret-key', algorithm='HS256')

        return jsonify({
            "status": "success",
            "access_token": token,
            "data": {
                "user_id": user.id,
                "username": user.name,  # 修复：使用 name
                "trust_score": user.trust_score
            }
        })

    except Exception as e:
        return jsonify({"status": "error", "message": f"登录异常: {str(e)}"}), 500
