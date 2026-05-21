# oa.py 新建文件，完整实现开题要求的3个核心接口+日志+容错机制
from flask import Blueprint, request, jsonify
from functools import wraps
import jwt
from models import db, User, OaAccessLog
from datetime import datetime

# 与现有系统JWT配置完全一致
JWT_SECRET_KEY = 'your-secret-key'
oa_bp = Blueprint('oa', __name__)


# -------------------------- 复用现有系统鉴权装饰器 --------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith('Bearer '):
            # 记录未授权访问日志
            _save_oa_log(0, '未知用户', 'login_check', '无有效token，访问被阻断', request.remote_addr, 'fail')
            return jsonify({"status": "error", "message": "未登录防护系统，禁止访问OA", "code": 401}), 401

        token = token.split(' ')[1]
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
            user_id = payload['user_id']
            current_user = User.query.get(user_id)
            if not current_user:
                _save_oa_log(0, '未知用户', 'login_check', '用户不存在，访问被阻断', request.remote_addr, 'fail')
                return jsonify({"status": "error", "message": "用户信息无效", "code": 401}), 401
        except jwt.ExpiredSignatureError:
            _save_oa_log(0, '未知用户', 'login_check', 'token过期，访问被阻断', request.remote_addr, 'fail')
            return jsonify({"status": "error", "message": "登录已过期，请重新登录", "code": 401}), 401
        except Exception:
            _save_oa_log(0, '未知用户', 'login_check', 'token校验失败，访问被阻断', request.remote_addr, 'fail')
            return jsonify({"status": "error", "message": "登录校验失败", "code": 401}), 401

        # 把当前用户传入视图函数
        kwargs['current_user'] = current_user
        return f(*args, **kwargs)

    return decorated_function


# -------------------------- 日志记录工具函数（全链路审计） --------------------------
def _save_oa_log(user_id, username, operate_type, operate_desc, client_ip, result):
    """统一记录OA访问日志，实现全链路溯源"""
    try:
        log = OaAccessLog(
            user_id=user_id,
            username=username,
            operate_type=operate_type,
            operate_desc=operate_desc,
            client_ip=client_ip,
            result=result
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"OA日志记录失败: {str(e)}")


# -------------------------- 开题要求的3个核心接口 --------------------------
@oa_bp.route('/check-login', methods=['GET'])
@login_required
def oa_check_login(**kwargs):
    """
    核心接口1：OA登录状态强制校验
    未登录直接被装饰器阻断，返回401；登录成功返回用户基础信息+登录状态
    """
    current_user = kwargs['current_user']
    # 记录访问日志
    _save_oa_log(
        current_user.id,
        current_user.username,
        'login_check',
        'OA登录状态校验通过',
        request.remote_addr,
        'success'
    )
    return jsonify({
        "status": "success",
        "is_login": True,
        "data": {
            "user_id": current_user.id,
            "username": current_user.username,
            "trust_score": current_user.trust_score
        }
    })


@oa_bp.route('/permission', methods=['GET'])
@login_required
def get_oa_permission(**kwargs):
    """
    核心接口2：OA权限同步（与用户信任值绑定，完全复用现有系统信任分逻辑）
    严格遵循开题要求的三级分级授权
    """
    current_user = kwargs['current_user']
    trust_score = current_user.trust_score

    # 权限分级规则与现有系统完全一致
    if trust_score >= 80:
        permission_level = "full"
        allow_functions = ["all", "file_export", "sensitive_file_view", "approval_urgent"]
        deny_functions = []
    elif 50 <= trust_score < 80:
        permission_level = "limit"
        allow_functions = ["base_view", "normal_approval", "file_browse"]
        deny_functions = ["file_export", "sensitive_file_view", "approval_urgent"]
    else:
        permission_level = "deny"
        allow_functions = []
        deny_functions = ["all"]

    # 记录权限查询日志
    _save_oa_log(
        current_user.id,
        current_user.username,
        'permission_sync',
        f'OA权限同步，信任分{trust_score}，权限等级{permission_level}',
        request.remote_addr,
        'success'
    )

    return jsonify({
        "status": "success",
        "data": {
            "trust_score": trust_score,
            "permission_level": permission_level,
            "allow_functions": allow_functions,
            "deny_functions": deny_functions
        }
    })


@oa_bp.route('/risk-alert', methods=['GET'])
@login_required
def get_user_risk_alert(**kwargs):
    """
    核心接口3：用户风险提醒同步（OA页面展示）
    """
    current_user = kwargs['current_user']
    # 可对接现有系统的告警表，此处为极简兼容实现
    risk_list = []
    # 示例：信任分低于60分添加风险提醒
    if current_user.trust_score < 60:
        risk_list.append({
            "level": "high",
            "content": "当前终端信任分过低，存在安全风险，已限制OA核心功能",
            "time": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        })

    # 记录风险查询日志
    _save_oa_log(
        current_user.id,
        current_user.username,
        'risk_query',
        'OA风险提醒查询',
        request.remote_addr,
        'success'
    )

    return jsonify({
        "status": "success",
        "data": {
            "risk_count": len(risk_list),
            "risk_list": risk_list
        }
    })


# -------------------------- 辅助接口：OA访问日志查询（审计溯源） --------------------------
@oa_bp.route('/access-log', methods=['GET'])
@login_required
def get_oa_access_log(**kwargs):
    """查询当前用户的OA访问日志，支持溯源"""
    current_user = kwargs['current_user']
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)

    # 分页查询当前用户的日志
    pagination = OaAccessLog.query.filter_by(user_id=current_user.id).order_by(OaAccessLog.created_at.desc()).paginate(
        page=page, per_page=page_size, error_out=False)
    log_list = [{
        "operate_type": log.operate_type,
        "operate_desc": log.operate_desc,
        "client_ip": log.client_ip,
        "result": log.result,
        "created_at": log.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for log in pagination.items]

    return jsonify({
        "status": "success",
        "data": {
            "total": pagination.total,
            "list": log_list
        }
    })