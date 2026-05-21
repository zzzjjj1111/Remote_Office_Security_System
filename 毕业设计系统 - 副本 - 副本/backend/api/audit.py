"""
审计日志API模块
提供审计日志查询和统计功能
"""

from flask import Blueprint, request, jsonify
from services.audit_service import audit_logger
from datetime import datetime
import logging

audit_bp = Blueprint('audit', __name__)
logger = logging.getLogger(__name__)


@audit_bp.route('/api/audit/logs', methods=['GET'])
def get_audit_logs():
    """
    查询审计日志
    
    Query Parameters:
        log_type: 日志类型过滤 (auth/permission/behavior/device/oa_access/system)
        user_id: 用户ID过滤
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        page: 页码 (默认1)
        per_page: 每页数量 (默认50)
    
    Returns:
        {
            "code": 200,
            "data": {
                "logs": [...],
                "total": 100,
                "page": 1,
                "per_page": 50,
                "pages": 2
            }
        }
    """
    try:
        # 获取查询参数
        log_type = request.args.get('log_type')
        user_id = request.args.get('user_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        # 【新增】获取搜索关键字
        keyword = request.args.get('keyword')
        
        # 转换日期格式
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
            # 包含结束日期的整天
            end_date = end_date.replace(hour=23, minute=59, second=59)
        
        # 调用服务层查询
        result = audit_logger.get_audit_logs(
            log_type=log_type,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            page=page,
            per_page=per_page,
            keyword=keyword  # 【新增】传递关键字
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"查询审计日志失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'查询失败: {str(e)}'
        }), 500


@audit_bp.route('/api/audit/statistics', methods=['GET'])
def get_audit_statistics():
    """
    获取审计统计数据
    
    Query Parameters:
        days: 统计天数 (默认7天)
    
    Returns:
        {
            "code": 200,
            "data": {
                "total_logs": 1000,
                "success_count": 950,
                "failure_count": 30,
                "warning_count": 20,
                "type_distribution": {
                    "auth": 200,
                    "permission": 150,
                    ...
                },
                "period_days": 7
            }
        }
    """
    try:
        days = request.args.get('days', 7, type=int)
        
        result = audit_logger.get_audit_statistics(days=days)
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"获取审计统计失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'统计失败: {str(e)}'
        }), 500


@audit_bp.route('/api/audit/user/<int:user_id>', methods=['GET'])
def get_user_audit_logs(user_id):
    """
    查询指定用户的审计日志
    
    Path Parameters:
        user_id: 用户ID
    
    Query Parameters:
        page: 页码 (默认1)
        per_page: 每页数量 (默认50)
    
    Returns:
        {
            "code": 200,
            "data": {
                "logs": [...],
                "total": 50,
                "page": 1,
                "per_page": 50
            }
        }
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        result = audit_logger.get_audit_logs(
            user_id=user_id,
            page=page,
            per_page=per_page
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"查询用户审计日志失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'查询失败: {str(e)}'
        }), 500


@audit_bp.route('/api/audit/logs/<int:log_id>/report', methods=['POST'])
def report_log_as_alert(log_id):
    """
    【新增】将日志审计中的日志上报为告警
    用于处理系统漏判的情况，支持全链路日志上报（行为/OA/审计等）
    
    Request Body:
        {
            "report_reason": "上报原因"
        }
    
    Returns:
        {
            "code": 200,
            "message": "上报成功",
            "data": {
                "alert_id": 新创建的告警ID
            }
        }
    """
    try:
        from core.db import db, Alert, BehaviorLog, AuditLog, OaAccessLog, User
        from datetime import datetime
        
        data = request.get_json() or {}
        report_reason = data.get('report_reason', '管理员人工上报')
        
        # 【修改】支持多种日志类型的上报
        # 1. 优先查找 BehaviorLog
        log = BehaviorLog.query.get(log_id)
        log_source = 'behavior'
        
        # 2. 如果没找到，尝试查找 AuditLog
        if not log:
            log = AuditLog.query.get(log_id)
            if log:
                log_source = 'audit'
        
        # 3. 如果还没找到，尝试查找 OaAccessLog
        if not log:
            log = OaAccessLog.query.get(log_id)
            if log:
                log_source = 'oa_access'
        
        if not log:
            return jsonify({
                'code': 404,
                'message': '日志不存在'
            }), 404
        
        # 检查是否已经上报过（避免重复）
        existing_alert = Alert.query.filter_by(log_id=log_id).first()
        if existing_alert:
            return jsonify({
                'code': 400,
                'message': '该日志已存在于告警列表中，无需重复上报'
            }), 400
        
        # 根据日志类型获取用户ID和操作详情
        if log_source == 'behavior':
            user_id = log.user_id
            action_detail = log.action_detail
            timestamp = log.timestamp
        elif log_source == 'audit':
            user_id = log.user_id
            action_detail = f'{log.action} - {log.description}'
            timestamp = log.created_at
        else:  # oa_access
            user_id = log.user_id
            action_detail = f'{log.operate_type} - {log.operate_desc}'
            timestamp = log.created_at
        
        # 创建新的告警记录
        alert = Alert(
            user_id=user_id,
            log_id=log.id,
            alert_level='medium',  # 人工上报默认为中风险
            action_taken='warn',
            description=f'[人工上报-{log_source}] {report_reason}. 原始操作：{action_detail}',
            created_at=datetime.now(),
            feedback_type='pending'  # 待处理
        )
        db.session.add(alert)
        
        # 同时降低用户信任分（人工上报意味着确实有问题）
        user = User.query.get(user_id)
        if user:
            old_score = user.trust_score
            user.trust_score = max(0, round(user.trust_score - 10, 2))  # 扣10分
            db.session.add(user)
            
            # 记录审计日志
            audit_logger.log_trust_score_update(
                user_id=user.id,
                old_score=old_score,
                new_score=user.trust_score,
                reason=f'管理员人工上报{log_source}日志违规行为'
            )
        
        db.session.commit()
        
        logger.info(f'日志 {log_id}({log_source}) 被管理员上报为告警，用户信任分已调整')
        
        return jsonify({
            'code': 200,
            'message': '上报成功，已生成告警并扣除信任分',
            'data': {
                'alert_id': alert.id,
                'new_trust_score': user.trust_score if user else None,
                'log_source': log_source
            }
        })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"上报日志失败: {e}")
        return jsonify({
            'code': 500,
            'message': f'上报失败: {str(e)}'
        }), 500
