from flask import Blueprint, request, jsonify
from core.db import db, User, BehaviorLog, Alert, AlgorithmConfig, AuditLog
from services.audit_service import audit_logger
from services.ac_service import acs_monitor
from datetime import datetime
import jwt as jwt_lib

oa_interaction_bp = Blueprint('oa_interaction', __name__)

@oa_interaction_bp.route('/oa/action', methods=['POST'])
def record_oa_action():
    """
    记录OA系统操作行为
    参数：
    - action_type: 操作类型 (approval/file_share/schedule/file_export/sensitive_view/urgent_approval)
    - action_detail: 操作详情
    - target_file: 目标文件（可选）
    """
    token = request.headers.get('Authorization', '')
    if not token or not token.startswith('Bearer '):
        return jsonify({"status": "error", "message": "未授权"}), 401
    
    try:
        # 解析token获取用户信息
        real_token = token.split(' ')[1]
        payload = jwt_lib.decode(real_token, 'your-secret-key', algorithms=['HS256'])
        user_id = payload['user_id']
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({"status": "error", "message": "用户不存在"}), 404
        
        data = request.json or {}
        action_type = data.get('action_type', '')
        action_detail = data.get('action_detail', '')
        target_file = data.get('target_file', '')
        
        # 1. 记录行为日志
        behavior_log = BehaviorLog(
            user_id=user_id,
            device_id=None,  # OA操作不关联具体设备
            behavior_type=f'oa_{action_type}',
            action_detail=action_detail,
            timestamp=datetime.now(),
            trust_score=user.trust_score,
            ip_address=request.remote_addr,
            network_type='office',
            is_vpn=False
        )
        db.session.add(behavior_log)
        db.session.flush()  # 获取log_id
        
        # 2. 敏感文件检测（AC自动机）
        is_sensitive = False
        sensitive_keywords = []
        if target_file:
            is_sensitive, sensitive_keywords = acs_monitor.is_sensitive(target_file)
            behavior_log.is_sensitive = is_sensitive
            db.session.commit()
        
        # 3. 工作时间检测
        config = AlgorithmConfig.query.first()
        current_time = datetime.now().strftime('%H:%M')
        is_work_time = False
        
        if config:
            work_start = config.work_start_time
            work_end = config.work_end_time
            is_work_time = work_start <= current_time <= work_end
        
        # 4. 风险判定逻辑
        risk_level = 'low'
        action_taken = 'warn'
        description = f'OA操作：{action_detail}'
        anomaly_score = 0.0
        
        # 非工作时间操作
        if not is_work_time:
            anomaly_score += 30
            description += ' [非工作时间操作]'
        
        # 敏感文件操作
        if is_sensitive:
            anomaly_score += 50
            risk_level = 'high'
            action_taken = 'block'
            description += f' [检测到敏感词：{", ".join(sensitive_keywords)}]'
        
        # 信任分低时访问敏感功能
        if user.trust_score < 50 and action_type in ['file_export', 'sensitive_view']:
            anomaly_score += 40
            risk_level = 'high'
            action_taken = 'block'
            description += ' [信任分不足]'
        
        # 5. 如果风险分超过阈值，生成告警
        if anomaly_score >= 40:
            alert = Alert(
                user_id=user_id,
                log_id=behavior_log.id,
                alert_level=risk_level,
                action_taken=action_taken,
                description=description,
                created_at=datetime.now()
            )
            db.session.add(alert)
            
            # 【新增】高风险阻断操作需要实时扣除信任分
            if action_taken == 'block':
                old_score = user.trust_score
                
                # 根据异常分数和敏感词综合判定扣分幅度
                if is_sensitive and anomaly_score >= 70:
                    # 敏感词 + 高风险：扣 15 分
                    deduction = 15
                elif is_sensitive:
                    # 仅敏感词：扣 10 分
                    deduction = 10
                elif anomaly_score >= 60:
                    # 非工作时间 + 信任分不足：扣 10 分
                    deduction = 10
                else:
                    # 一般违规：扣 5 分
                    deduction = 5
                
                user.trust_score = max(0, round(user.trust_score - deduction, 2))
                db.session.add(user)
                
                print(f"🚨 OA操作违规阻断：用户 {user.name} 信任分 {old_score:.2f} → {user.trust_score:.2f} (扣除 {deduction} 分)")
                
                # 记录审计日志
                try:
                    audit_logger.log_trust_score_update(
                        user_id=user_id,
                        old_score=old_score,
                        new_score=user.trust_score,
                        reason=f'OA操作违规阻断：{description}'
                    )
                except Exception as e:
                    print(f"⚠️ 审计日志记录失败: {e}")
            
            # 【修改】如果是阻断操作，记录审计日志并按系统分类
            if action_taken == 'block':
                # 根据 action_type 判断属于哪个系统
                system_type = 'approval'  # 默认协同审批系统
                if action_type in ['file_share', 'file_export']:
                    system_type = 'source_code'  # 文件共享/导出归类到源码仓库
                elif action_type in ['urgent_approval', 'approval']:
                    system_type = 'approval'  # 审批相关归类到协同审批
                
                audit_logger.log_behavior(
                    user_id=user_id,
                    device_id=None,
                    behavior_type='oa_action_blocked',
                    description=f'OA操作被阻断：{description}',
                    anomaly_score=anomaly_score / 100.0  # 转换为 0-1 范围
                )
                
                # 修改日志类型为对应系统
                from core.db import AuditLog
                latest_log = AuditLog.query.filter_by(
                    user_id=user_id, 
                    action='oa_action_blocked'
                ).order_by(AuditLog.id.desc()).first()
                if latest_log:
                    latest_log.log_type = system_type
                    db.session.commit()
                
                print(f"[Audit] 记录{system_type}系统阻断日志: {description}")
        
        db.session.commit()
        
        return jsonify({
            "status": "success",
            "message": "操作已记录",
            "data": {
                "is_blocked": action_taken == 'block',
                "risk_level": risk_level,
                "anomaly_score": anomaly_score,
                "is_work_time": is_work_time,
                "is_sensitive": is_sensitive,
                "block_reason": description if action_taken == 'block' else None
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


@oa_interaction_bp.route('/oa/work-time', methods=['GET'])
def get_work_time():
    """获取工作时间配置"""
    try:
        config = AlgorithmConfig.query.first()
        if not config:
            config = AlgorithmConfig(
                trust_threshold=60,
                wma_weight=0.5,
                work_start_time="09:30",
                work_end_time="18:30"
            )
            db.session.add(config)
            db.session.commit()
        
        return jsonify({
            "status": "success",
            "data": {
                "work_start_time": config.work_start_time,
                "work_end_time": config.work_end_time
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@oa_interaction_bp.route('/oa/work-time', methods=['POST'])
def update_work_time():
    """更新工作时间配置（仅管理员）"""
    token = request.headers.get('Authorization', '')
    if not token or not token.startswith('Bearer '):
        return jsonify({"status": "error", "message": "未授权"}), 401
    
    try:
        # 解析token
        real_token = token.split(' ')[1]
        payload = jwt_lib.decode(real_token, 'your-secret-key', algorithms=['HS256'])
        user_id = payload['user_id']
        user = User.query.get(user_id)
        
        # 检查是否为管理员
        if user.position != '系统管理员':
            return jsonify({"status": "error", "message": "权限不足，仅管理员可修改"}), 403
        
        data = request.json or {}
        work_start_time = data.get('work_start_time', '09:30')
        work_end_time = data.get('work_end_time', '18:30')
        
        # 验证时间格式
        try:
            datetime.strptime(work_start_time, '%H:%M')
            datetime.strptime(work_end_time, '%H:%M')
        except ValueError:
            return jsonify({"status": "error", "message": "时间格式错误，应为 HH:MM"}), 400
        
        config = AlgorithmConfig.query.first()
        if not config:
            config = AlgorithmConfig(trust_threshold=60, wma_weight=0.5)
            db.session.add(config)
        
        old_start = config.work_start_time
        old_end = config.work_end_time
        config.work_start_time = work_start_time
        config.work_end_time = work_end_time
        config.updated_at = datetime.now()
        db.session.commit()
        
        # 记录审计日志
        audit_logger.log_system(
            user_id=user_id,
            action='update_work_time',
            status='success',
            description=f'修改工作时间：{old_start}-{old_end} → {work_start_time}-{work_end_time}',
            old_value=f'{old_start}-{old_end}',
            new_value=f'{work_start_time}-{work_end_time}'
        )
        
        return jsonify({
            "status": "success",
            "message": "工作时间已更新",
            "data": {
                "work_start_time": work_start_time,
                "work_end_time": work_end_time
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
