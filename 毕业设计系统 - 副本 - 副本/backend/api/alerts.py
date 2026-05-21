from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from core.db import db, Alert, User, Device, BehaviorLog, FalsePositiveSample, AlgorithmConfig
from services.ml_service import train_isolation_forest
import logging

alerts_bp = Blueprint('alerts', __name__)
logger = logging.getLogger(__name__)


# 自定义认证装饰器，支持 JWT Token
def jwt_required(f):
    from functools import wraps
    import jwt as jwt_lib

    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '')
        if not token or not token.startswith('Bearer '):
            return jsonify({'code': 401, 'message': '未提供有效 Token'}), 401
        try:
            real_token = token.split(' ')[1]
            # 解析 JWT Token
            payload = jwt_lib.decode(real_token, 'your-secret-key', algorithms=['HS256'])
            user_id = payload['user_id']
            # 将 user_id 放入 request 上下文供路由使用
            request.current_user_id = user_id
        except jwt_lib.ExpiredSignatureError:
            return jsonify({'code': 401, 'message': 'Token 已过期'}), 401
        except jwt_lib.InvalidTokenError:
            return jsonify({'code': 401, 'message': 'Token 解析失败'}), 401
        except Exception as e:
            return jsonify({'code': 401, 'message': f'Token 验证失败: {str(e)}'}), 401
        return f(*args, **kwargs)

    return decorated


def get_jwt_identity():
    return getattr(request, 'current_user_id', None)


@alerts_bp.route('/api/alerts', methods=['GET'])
@jwt_required
def get_alerts():
    """获取告警列表（支持分页和筛选）"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        alert_level = request.args.get('alert_level')
        status = request.args.get('status')
        is_false_positive = request.args.get('is_false_positive', type=int)

        query = Alert.query

        # 筛选条件
        if alert_level:
            query = query.filter_by(alert_level=alert_level)
        if status == 'pending':
            query = query.filter(Alert.feedback_type == 'pending')
        elif status == 'processed':
            query = query.filter(Alert.feedback_type != 'pending')
        if is_false_positive is not None:
            query = query.filter_by(is_false_positive=bool(is_false_positive))

        # 分页
        pagination = query.order_by(Alert.id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # 【性能优化】批量查询用户和行为日志，避免 N+1 查询
        alert_items = pagination.items
        user_ids = list(set([a.user_id for a in alert_items if a.user_id]))
        log_ids = list(set([a.log_id for a in alert_items if a.log_id]))

        # 一次性查询所有用户
        users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}
        # 一次性查询所有行为日志
        logs = {l.id: l for l in BehaviorLog.query.filter(BehaviorLog.id.in_(log_ids)).all()} if log_ids else {}

        alerts = []
        for alert in alert_items:
            user = users.get(alert.user_id)
            log = logs.get(alert.log_id) if alert.log_id else None

            alert_data = {
                'id': alert.id,
                'user_id': alert.user_id,
                'user_name': user.name if user else 'Unknown',
                'alert_level': alert.alert_level,
                'action_taken': alert.action_taken,
                'description': alert.description,
                'timestamp': alert.created_at.isoformat() if alert.created_at else None,
                'is_false_positive': alert.is_false_positive,
                'feedback_type': alert.feedback_type,
                'feedback_time': alert.feedback_time.isoformat() if alert.feedback_time else None,
                'feedback_reason': alert.feedback_reason,
                'baseline_corrected': alert.baseline_corrected,
                'correction_time': alert.correction_time.isoformat() if alert.correction_time else None,
            }

            # 添加上下文信息
            if log:
                alert_data.update({
                    'behavior_type': log.behavior_type,
                    'action_detail': log.action_detail,
                    'anomaly_score': log.anomaly_score,
                    'network_type': log.network_type,
                    'location_hint': log.location_hint,
                    'ip_address': log.ip_address
                })

            alerts.append(alert_data)

        return jsonify({
            'code': 200,
            'data': {
                'alerts': alerts,
                'total': pagination.total,
                'page': page,
                'per_page': per_page,
                'pages': pagination.pages
            }
        })

    except Exception as e:
        logger.error(f'获取告警列表失败: {str(e)}')
        return jsonify({'code': 500, 'message': str(e)}), 500


@alerts_bp.route('/api/alerts/<int:alert_id>/feedback', methods=['POST'])
@jwt_required
def submit_feedback(alert_id):
    """提交误判反馈"""
    try:
        admin_id = get_jwt_identity()
        data = request.get_json()

        feedback_type = data.get('feedback_type')  # 'false_positive' 或 'confirmed'
        feedback_reason = data.get('feedback_reason', '')

        if feedback_type not in ['false_positive', 'confirmed']:
            return jsonify({'code': 400, 'message': '反馈类型必须为 false_positive 或 confirmed'}), 400

        # 查找告警
        alert = Alert.query.get(alert_id)
        if not alert:
            return jsonify({'code': 404, 'message': '告警不存在'}), 404

        # 更新告警反馈信息
        now = datetime.now()
        alert.feedback_type = feedback_type
        alert.feedback_time = now
        alert.feedback_reason = feedback_reason
        alert.feedback_admin_id = admin_id

        if feedback_type == 'false_positive':
            alert.is_false_positive = True

            # 记录误判样本
            log = BehaviorLog.query.get(alert.log_id) if alert.log_id else None
            sample = FalsePositiveSample(
                alert_id=alert.id,
                user_id=alert.user_id,
                device_id=log.device_id if log else None,
                behavior_type=log.behavior_type if log else None,
                anomaly_score=log.anomaly_score if log else None,
                feedback_reason=feedback_reason
            )
            db.session.add(sample)

            # 【新增】自动恢复用户信任分（误报补偿）
            user = User.query.get(alert.user_id)
            if user:
                old_score = user.trust_score
                
                # 【核心修复】根据告警记录的实际扣分数值进行精确恢复
                deducted = alert.trust_score_deducted if alert.trust_score_deducted else 0.0
                
                if deducted > 0:
                    # 有记录的扣分：精确加回扣掉的分数
                    restore_score = deducted
                    print(f'✅ [误报恢复] 告警 #{alert_id} 原扣 {deducted:.2f} 分，现加回 {restore_score:.2f} 分')
                else:
                    # 无记录或旧数据：默认加10分（兼容旧逻辑）
                    restore_score = 10.0
                    print(f'⚠️ [误报恢复] 告警 #{alert_id} 无扣分记录，使用默认加分: {restore_score:.2f} 分')
                
                # 加分后不超过100分
                user.trust_score = min(100.0, round(user.trust_score + restore_score, 2))
                db.session.add(user)
                logger.info(f'误报处理：用户 {user.name} 信任分恢复 {old_score:.2f} → {user.trust_score:.2f} (加回{restore_score:.2f}分)')

                # 记录审计日志
                try:
                    from services.audit_service import audit_logger
                    audit_logger.log_trust_score_update(
                        user_id=user.id,
                        old_score=old_score,
                        new_score=user.trust_score,
                        reason=f'管理员标记告警 #{alert_id} 为误报，自动恢复信任分(+{restore_score:.2f}分)'
                    )
                except Exception as e:
                    logger.warning(f'审计日志记录失败: {e}')

            # 尝试自动修正基线
            try:
                _auto_correct_baseline(alert.user_id, log)
                alert.baseline_corrected = True
                alert.correction_time = datetime.now()
                logger.info(f'告警 {alert_id} 误判反馈已记录，基线已自动修正')
            except Exception as e:
                logger.error(f'基线修正失败: {str(e)}')
                # 即使基线修正失败，也要保存反馈
                alert.baseline_corrected = False

        db.session.commit()

        return jsonify({
            'code': 200,
            'message': '反馈提交成功',
            'data': {
                'alert_id': alert.id,
                'feedback_type': feedback_type,
                'baseline_corrected': alert.baseline_corrected
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f'提交反馈失败: {str(e)}')
        return jsonify({'code': 500, 'message': str(e)}), 500


@alerts_bp.route('/api/alerts/<int:alert_id>', methods=['PUT'])
@jwt_required
def update_alert_status(alert_id):
    """更新告警状态（标记为误报/已处置等）"""
    try:
        admin_id = get_jwt_identity()
        data = request.get_json()

        action = data.get('action')  # 'false_positive', 'block', 'warn', etc.

        alert = Alert.query.get(alert_id)
        if not alert:
            return jsonify({'code': 404, 'message': '告警不存在'}), 404

        # 根据动作更新状态
        if action == 'false_positive':
            alert.feedback_type = 'false_positive'
            alert.is_false_positive = True
            alert.feedback_time = datetime.now()
            alert.feedback_admin_id = admin_id
        elif action in ['block', 'warn']:
            alert.feedback_type = 'confirmed'
            alert.action_taken = action

        db.session.commit()

        return jsonify({'code': 200, 'message': '状态更新成功'})

    except Exception as e:
        db.session.rollback()
        logger.error(f'更新告警状态失败: {str(e)}')
        return jsonify({'code': 500, 'message': str(e)}), 500


@alerts_bp.route('/api/alerts/false-positives/stats', methods=['GET'])
@jwt_required
def get_false_positive_stats():
    """获取误判统计信息"""
    try:
        total_alerts = Alert.query.count()
        false_positives = Alert.query.filter_by(is_false_positive=True).count()
        confirmed = Alert.query.filter_by(feedback_type='confirmed').count()
        pending = Alert.query.filter_by(feedback_type='pending').count()

        # 按用户统计误判率
        user_stats = db.session.query(
            User.id,
            User.name,
            db.func.count(Alert.id).label('total_alerts'),
            db.func.sum(db.case((Alert.is_false_positive == True, 1), else_=0)).label('false_positives')
        ).join(Alert, User.id == Alert.user_id).group_by(User.id).all()

        user_false_positive_rates = []
        for user_id, user_name, total, fp_count in user_stats:
            rate = (fp_count / total * 100) if total > 0 else 0
            user_false_positive_rates.append({
                'user_id': user_id,
                'user_name': user_name,
                'total_alerts': total,
                'false_positives': fp_count,
                'false_positive_rate': round(rate, 2)
            })

        return jsonify({
            'code': 200,
            'data': {
                'total_alerts': total_alerts,
                'false_positives': false_positives,
                'confirmed': confirmed,
                'pending': pending,
                'false_positive_rate': round((false_positives / total_alerts * 100), 2) if total_alerts > 0 else 0,
                'user_stats': user_false_positive_rates[:10]  # 前10名
            }
        })

    except Exception as e:
        logger.error(f'获取误判统计失败: {str(e)}')
        return jsonify({'code': 500, 'message': str(e)}), 500


def _auto_correct_baseline(user_id, log):
    """自动修正用户基线（内部函数）"""
    try:
        if not log:
            return

        # 1. 更新WMA基线参数（降低该行为类型的权重）
        config = AlgorithmConfig.query.first()
        if config and config.baseline_data:
            import json
            baseline = json.loads(config.baseline_data)

            # 找到该用户的基线数据
            user_baseline_key = f'user_{user_id}'
            if user_baseline_key in baseline:
                user_data = baseline[user_baseline_key]

                # 如果是特定行为类型被误判，降低该类型的敏感度
                behavior_type = log.behavior_type
                if behavior_type and behavior_type in user_data.get('behavior_patterns', {}):
                    # 降低该行为类型的异常阈值
                    pattern = user_data['behavior_patterns'][behavior_type]
                    if 'threshold' in pattern:
                        pattern['threshold'] = min(pattern['threshold'] * 1.2, 100)  # 提高阈值20%
                        logger.info(f'已调整用户 {user_id} 的行为 {behavior_type} 阈值')

                # 保存更新后的基线
                config.baseline_data = json.dumps(baseline, ensure_ascii=False)
                db.session.commit()

        # 2. 标记该样本用于重新训练孤立森林模型
        # 这里只是标记，实际训练由定时任务或手动触发
        logger.info(f'用户 {user_id} 的误判样本已记录，将在下次模型训练时使用')

    except Exception as e:
        logger.error(f'自动修正基线失败: {str(e)}')
        raise


@alerts_bp.route('/api/alerts/retrain-model', methods=['POST'])
@jwt_required
def trigger_model_retrain():
    """手动触发模型重新训练（使用误判样本）"""
    try:
        # 获取所有未用于训练的误判样本
        unused_samples = FalsePositiveSample.query.filter_by(used_for_training=False).all()

        if not unused_samples:
            return jsonify({
                'code': 200,
                'message': '没有未使用的误判样本',
                'data': {'samples_count': 0}
            })

        # 调用ML服务重新训练
        result = train_isolation_forest(include_false_positives=True)

        # 标记样本已用于训练
        now = datetime.now()
        for sample in unused_samples:
            sample.used_for_training = True
            sample.training_time = now

        db.session.commit()

        return jsonify({
            'code': 200,
            'message': '模型重新训练成功',
            'data': {
                'samples_used': len(unused_samples),
                'training_result': result
            }
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f'模型重新训练失败: {str(e)}')
        return jsonify({'code': 500, 'message': str(e)}), 500


@alerts_bp.route('/api/alerts/decision', methods=['POST'])
def handle_user_decision():
    """
    处理用户对敏感操作的二次确认决策

    信任分变化规则（基于交叉决策矩阵）：
    - 确认继续：净扣 3 分（原扣5分 + 配合系统奖励2分）
    - 取消操作：净扣 5 分（不作奖励）
    - 上报管理员：净扣 5 分（等待审批，不予奖励）

    Request Body:
    {
        'log_id': 123,
        'user_id': 456,
        'decision': 'allow' / 'block' / 'report'
    }
    """
    try:
        data = request.get_json()
        log_id = data.get('log_id')
        user_id = data.get('user_id')
        decision = data.get('decision')  # 'allow' / 'block' / 'report'

        if not all([log_id, user_id, decision]):
            return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400

        if decision not in ['allow', 'block', 'report']:
            return jsonify({'status': 'error', 'message': '决策类型无效'}), 400

        # 查找行为日志
        log = BehaviorLog.query.get(log_id)
        if not log:
            return jsonify({'status': 'error', 'message': '日志不存在'}), 404

        # 查找或创建告警
        alert = Alert.query.filter_by(log_id=log_id).first()
        if not alert:
            # 创建新告警
            alert = Alert(
                user_id=user_id,
                log_id=log_id,
                alert_level='high',
                action_taken='warn',  # 默认警告
                description=f"敏感文件操作待确认: {log.action_detail}"
            )
            db.session.add(alert)
            db.session.flush()

        user = User.query.get(user_id)

        # ========== 【核心修改】根据决策处理信任分 ==========
        #
        # behavior.py 触发 confirm_required 时已预扣 5 分
        # 此处根据用户协作程度给予不同恢复：
        #   - confirm = +2 → 净扣 3 分（配合系统有小奖励）
        #   - block/report = +0 → 净扣 5 分（不配合则无奖励）
        # =================================================

        if decision == 'allow':
            # 用户确认继续 — 配合系统，小额恢复
            alert.action_taken = 'warn'
            alert.description += ' [用户确认继续]'
            alert.feedback_type = 'user_confirmed'

            # 【修复】用户确认继续，不奖励分数，保持净扣5分
            # 之前预扣了5分，现在不加回，避免持续加分的问题
            if user:
                old_score = user.trust_score
                # 不加分，保持净扣5分
                try:
                    print(f"✅ 用户 {user_id} 确认继续 | 信任分: {old_score:.2f} (净扣5分)")
                except OSError:
                    # Windows控制台编码问题时的备选方案
                    print(f"User {user_id} confirmed action | Trust score: {old_score:.2f} (net -5 points)")

        elif decision == 'block':
            # 用户取消操作 — 不配合，不恢复
            alert.action_taken = 'block'
            alert.description += ' [用户取消操作]'
            alert.feedback_type = 'user_cancelled'

            if user:
                old_score = user.trust_score
                # 不加回，净扣 5 分
                try:
                    print(f"❌ 用户 {user_id} 取消操作 | 信任分: {old_score:.2f} (净扣5分)")
                except OSError:
                    # Windows控制台编码问题时的备选方案
                    print(f"User {user_id} cancelled operation | Trust score: {old_score:.2f} (net -5 points)")

        elif decision == 'report':
            # 上报管理员 — 不确定，不恢复
            alert.action_taken = 'warn'
            alert.description += ' [已上报管理员，等待审批]'
            alert.feedback_type = 'pending_review'

            if user:
                old_score = user.trust_score
                # 不加回，净扣 5 分
                try:
                    print(f"📋 用户 {user_id} 上报管理员 | 信任分: {old_score:.2f} (净扣5分)")
                except OSError:
                    # Windows控制台编码问题时的备选方案
                    print(f"User {user_id} reported to admin | Trust score: {old_score:.2f} (net -5 points)")

        db.session.add(alert)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': '决策已处理',
            'data': {
                'alert_id': alert.id,
                'action_taken': alert.action_taken,
                'trust_score': round(user.trust_score, 2) if user else None
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ 处理用户决策失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@alerts_bp.route('/api/alerts/<int:alert_id>/execute-block', methods=['POST'])
@jwt_required
def execute_remote_block(alert_id):
    """管理员远程阻断用户登录"""
    try:
        admin_id = get_jwt_identity()
        alert = Alert.query.get(alert_id)
        if not alert:
            return jsonify({'code': 404, 'message': '告警不存在'}), 404
        
        # 【修改】直接更新用户状态为blocked，禁止登录
        user = User.query.get(alert.user_id)
        if not user:
            return jsonify({'code': 404, 'message': '用户不存在'}), 404
        
        old_status = user.status
        user.status = 'blocked'
        
        # 更新告警状态
        alert.action_taken = 'block'
        alert.feedback_type = 'admin_blocked'
        alert.feedback_time = datetime.now()
        alert.feedback_admin_id = admin_id
        db.session.commit()
        
        logger.info(f'管理员 {admin_id} 已阻断用户 {user.name}(ID:{user.id}) 的登录权限')
        
        return jsonify({
            'code': 200,
            'message': f'用户 {user.name} 已被阻断，无法再登录系统',
            'data': {
                'alert_id': alert_id,
                'user_id': user.id,
                'user_name': user.name,
                'old_status': old_status,
                'new_status': 'blocked'
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f'执行远程阻断失败: {str(e)}')
        return jsonify({'code': 500, 'message': str(e)}), 500


@alerts_bp.route('/api/users/<int:user_id>/unblock', methods=['POST'])
@jwt_required
def unblock_user(user_id):
    """管理员解除用户阻断"""
    try:
        admin_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'code': 404, 'message': '用户不存在'}), 404
        
        if user.status != 'blocked':
            return jsonify({'code': 400, 'message': '用户当前未被阻断'}), 400
        
        # 解除阻断
        user.status = 'active'
        db.session.commit()
        
        logger.info(f'管理员 {admin_id} 已解除用户 {user.name}(ID:{user_id}) 的阻断')
        
        return jsonify({
            'code': 200,
            'message': f'用户 {user.name} 已解除阻断，可以正常登录',
            'data': {
                'user_id': user_id,
                'user_name': user.name,
                'status': 'active'
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f'解除阻断失败: {str(e)}')
        return jsonify({'code': 500, 'message': str(e)}), 500
