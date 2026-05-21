from flask import Blueprint, jsonify, request
from core.db import db, User, Device, BehaviorLog, Alert, SensitiveWord
from services.ac_service import acs_monitor
from services.ml_service import BehaviorAnalyzer
from services.health_check_service import TerminalHealthChecker  # 【新增】健康检查服务
from services.trust_score_service import trust_calculator  # 【新增】信任值计算服务
from services.audit_service import audit_logger  # 【新增】审计日志服务
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import json

# 创建行为分析器实例
analyzer = BehaviorAnalyzer()
behavior_bp = Blueprint('behavior', __name__)

SECRET_KEY = b'1234567890123456'
IV = b'1234567890123456'


def decrypt_data(encrypted_hex):
    try:
        cipher = Cipher(algorithms.AES(SECRET_KEY), modes.CBC(IV), backend=default_backend())
        decryptor = cipher.decryptor()
        encrypted_bytes = bytes.fromhex(encrypted_hex)
        decrypted_padded = decryptor.update(encrypted_bytes) + decryptor.finalize()
        # 去除 padding
        pad_len = decrypted_padded[-1]
        decrypted = decrypted_padded[:-pad_len].decode('utf-8')
        return json.loads(decrypted)
    except Exception as e:
        print("Decryption error:", e)
        return None


# 确认是 @behavior_bp.route，不是 @app.route
@behavior_bp.route('/alerts', methods=['GET'])
def get_alerts():
    """获取所有告警记录"""
    try:
        from sqlalchemy import func
        # 查询所有告警，关联用户信息
        alerts = db.session.query(Alert, User).join(User, Alert.user_id == User.id).order_by(
            Alert.id.desc()).all()

        result = []
        for alert, user in alerts:
            log = db.session.query(BehaviorLog).filter_by(id=alert.log_id).first()
            result.append({
                "id": alert.id,
                "user_name": user.name,
                "alert_level": alert.alert_level,
                "action_taken": alert.action_taken,
                "description": alert.description,
                "status": "已处置" if alert.action_taken == "block" else "待处理",
                "behavior_type": log.behavior_type if log else "未知",
                "timestamp": log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log and log.timestamp else "未知时间"
            })

        return jsonify({
            "status": "success",
            "data": result
        })
    except Exception as e:
        print("Error fetching alerts:", e)
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@behavior_bp.route('/logs', methods=['GET'])
def get_logs():
    """获取最新的行为日志（默认10条）"""
    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)  # 默认改为10条

        # 【性能优化】直接在数据库层面限制查询数量，而不是查询全部
        # 使用limit()限制结果集大小，大幅提升查询速度
        logs = db.session.query(BehaviorLog, User, Alert).outerjoin(
            User, BehaviorLog.user_id == User.id
        ).outerjoin(Alert, Alert.log_id == BehaviorLog.id).order_by(
            BehaviorLog.timestamp.desc()
        ).limit(per_page).all()  # 【关键】添加limit限制

        result = []
        for log, user, alert in logs:
            time_str = log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else "未知时间"
            action = "pass"
            level = "info"
            if alert:
                action = alert.action_taken
                level = alert.alert_level

            result.append({
                "id": log.id,
                "time": time_str,
                "timestamp": log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else None,
                "user": user.name if user else "未知用户",
                "type": log.behavior_type,
                "detail": log.action_detail,
                "action_taken": action,
                "alert_level": level,
                "anomaly_score": log.anomaly_score,
                "description": log.action_detail,
                "behavior_type": log.behavior_type
            })

        return jsonify({
            "code": 200,
            "status": "success",
            "data": {
                "logs": result,
                "total": len(result),
                "page": page,
                "per_page": per_page
            }
        })
    except Exception as e:
        print("Error fetching logs:", e)
        import traceback
        traceback.print_exc()
        return jsonify({"code": 500, "status": "error", "message": str(e)}), 500


@behavior_bp.route('/upload', methods=['POST'])
def upload_behavior():
    """接收终端上传的加密数据，并进行初步落库与分析触发"""
    payload = request.json

    # 支持前端模拟器的明文注入
    if payload.get("is_frontend_mock"):
        data = payload
        user_id = payload.get("mock_user_id")
        user = User.query.get(user_id) if user_id else None
        mac_address = data.get("mac_address")
        device = None  # 【修复】初始化 device 变量

        # 顺便确保有这个设备
        if user:
            mock_dev = Device.query.filter_by(mac_address=mac_address).first()
            if not mock_dev:
                mock_dev = Device(mac_address=mac_address, user_id=user.id)
                db.session.add(mock_dev)
                db.session.commit()
            device = mock_dev

        # 【修改】终端健康基线检查：如果Agent上报了健康数据，自动触发检查
        patch_status = data.get("patch_status")
        antivirus_status = data.get("antivirus_status")

        if patch_status and antivirus_status:
            try:
                health_result = TerminalHealthChecker.check_device_health(
                    mac_address=mac_address,
                    patch_status=patch_status,
                    antivirus_status=antivirus_status,
                    user_id=user_id
                )
                try:
                    print(f"[Health Check] 设备 {mac_address} 健康检查结果: {health_result['compliance_status']}")
                except OSError:
                    # Windows控制台编码问题时的备选方案
                    print(f"[Health Check] Device {mac_address} health check result: {health_result['compliance_status']}")
            except Exception as e:
                try:
                    print(f"⚠️ [Health Check] 健康检查失败: {e}")
                except OSError:
                    # Windows控制台编码问题时的备选方案
                    print(f"⚠️ [Health Check] Health check failed: {e}")
                # 健康检查失败不影响主流程
    else:
        # 原有的加密逻辑
        encrypted_data = payload.get("encrypted_data")
        if not encrypted_data:
            return jsonify({"status": "error", "message": "No data"}), 400

        data = decrypt_data(encrypted_data)
        if not data:
            return jsonify({"status": "error", "message": "Decryption failed"}), 400

        mac_address = data.get("mac_address")
        device = Device.query.filter_by(mac_address=mac_address).first()
        if not device or not device.user_id:
            return jsonify({"status": "ignored", "message": "Unregistered device or unbound user"}), 200
        user = User.query.get(device.user_id)

    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    # 【修复】确保 device 存在，如果不存在则创建
    if not device:
        mock_dev = Device.query.filter_by(mac_address=mac_address).first()
        if not mock_dev:
            mock_dev = Device(mac_address=mac_address, user_id=user.id)
            db.session.add(mock_dev)
            db.session.commit()
        device = mock_dev

    action_detail = data.get("action_detail", "")
    behavior_type = data.get("behavior_type")

    # 【新增】打印后端接收到的原始数据，用于调试漏检问题
    try:
        print(f"🔍 [Backend Debug] 收到上报 - 行为类型: {behavior_type}")
        print(f"🔍 [Backend Debug] action_detail: {action_detail}")
        print(f"🔍 [Backend Debug] file_operation: {data.get('file_operation')}")
    except OSError:
        # Windows控制台编码问题时的备选方案
        print(f"[Backend Debug] Received report - behavior type: {behavior_type}")
        print(f"[Backend Debug] action_detail: {action_detail}")
        print(f"[Backend Debug] file_operation: {data.get('file_operation')}")

    # 【核心修复】根据behavior_type设置特殊标记，用于精准风险判定
    is_usb_copy = behavior_type in ['usb_copy', 'usb_access']
    is_email_send = behavior_type in ['email_send', 'email_with_attachment']
    is_screen_sharing_detected = behavior_type in ['remote_control_sharing', 'system_screen_sharing', 'video_conference_sharing']
    is_sensitive_website = behavior_type == 'sensitive_website_visit'
    is_sensitive_file = behavior_type in ['sensitive_file_access', 'sensitive_directory_access']

    # 1. AC自动机检测敏感词 (显性违规) —— 原有逻辑，完全保留
    is_sens, matched_words = acs_monitor.is_sensitive(action_detail)
    try:
        print(f"🔍 [AC检测] action_detail 检测结果: is_sens={is_sens}, matched_words={matched_words}")
    except OSError:
        # Windows控制台编码问题时的备选方案
        print(f"[AC Detection] action_detail detection result: is_sens={is_sens}, matched_words={matched_words}")
    
    # 【核心修复】如果 action_detail 没命中，但 file_operation 命中了，也要判定为敏感
    if not is_sens:
        file_op_str = str(data.get('file_operation', ''))
        is_sens, matched_words = acs_monitor.is_sensitive(file_op_str)
        try:
            print(f"🔍 [AC检测] file_operation 检测结果: is_sens={is_sens}, matched_words={matched_words}")
        except OSError:
            # Windows控制台编码问题时的备选方案
            print(f"[AC Detection] file_operation detection result: is_sens={is_sens}, matched_words={matched_words}")
        if is_sens:
            try:
                print(f"✅ [Backend Debug] 在 file_operation 中命中敏感词: {matched_words}")
            except OSError:
                # Windows控制台编码问题时的备选方案
                print(f"[Backend Debug] Matched sensitive words in file_operation: {matched_words}")
            # 将敏感信息同步到 action_detail，方便后续日志展示
            action_detail = f"{action_detail} | 文件操作详情: {file_op_str}"

    # 2. 原有孤立森林异常检测
    current_features = analyzer.extract_behavior_features([
        BehaviorLog(
            user_id=user.id,
            behavior_type=behavior_type,
            is_sensitive=is_sens,
            # 移除 cpu_usage，因为 BehaviorLog 模型中没有这个字段
        )
    ])

    isolate_anomaly_score = analyzer.get_isolation_forest_score(current_features)

    # 【新增】构建上下文数据
    context_data = {
        'network_type': data.get('network_type', 'unknown'),
        'is_vpn': data.get('is_vpn', False),
        'location_hint': data.get('location_hint', '未知位置')
    }

    # 计算双基线异常分（岗位基线+个人动态基线）+ 上下文折扣
    baseline_result = analyzer.detect_anomaly_by_baseline(user.id, current_features, context=context_data)
    baseline_anomaly_score = baseline_result['final_score'] * 100  # 使用折扣后的分数

    # 综合异常分：孤立森林(50%) + 双基线(50%) → 更精准
    final_anomaly_score = (isolate_anomaly_score + baseline_anomaly_score) / 2

    # 记录折扣信息（用于日志）
    discount_info = {
        'raw_score': baseline_result['raw_score'],
        'discount_factor': baseline_result['discount_factor'],
        'final_score': baseline_result['final_score'],
        'context': context_data
    }
    # ==================================================================================

    # 3. 【核心修改】按照 40+30+30 权重重新计算信任值基线
    current_behavior_data = {
        'behavior_type': behavior_type,
        'is_sensitive': is_sens
    }

    trust_result = trust_calculator.calculate_trust_score(
        user_id=user.id,
        device_mac=mac_address,
        current_behavior=current_behavior_data,
        context=context_data
    )

    baseline_trust = trust_result['total_score']

    try:
        print(f"\n{'=' * 60}")
        print(f"📊 信任值计算详情 (用户: {user.name})")
        print(f"{'=' * 60}")
        print(f"   身份认证得分: {trust_result['auth_score']:.2f} / 40")
        print(f"   设备健康得分: {trust_result['health_score']:.2f} / 30")
        print(f"   行为基线得分: {trust_result['behavior_score']:.2f} / 30")
        print(f"   ──────────────────────")
        print(f"   总信任分值: {baseline_trust:.2f} / 100")
        print(f"{'=' * 60}\n")
    except OSError:
        # Windows控制台编码问题时的备选方案
        print(f"\n{'=' * 60}")
        print(f"Trust Score Calculation Details (User: {user.name})")
        print(f"{'=' * 60}")
        print(f"   Auth Score: {trust_result['auth_score']:.2f} / 40")
        print(f"   Health Score: {trust_result['health_score']:.2f} / 30")
        print(f"   Behavior Score: {trust_result['behavior_score']:.2f} / 30")
        print(f"   ──────────────────────")
        print(f"   Total Trust Score: {baseline_trust:.2f} / 100")
        print(f"{'=' * 60}\n")

    # 4. 动态响应决策（基于交叉决策矩阵）
    action_taken = "pass"
    alert_level = "low"
    
    # 初始化 new_trust_score 为原分数（正常行为不扣分）
    new_trust_score = user.trust_score
    
    # 【新增】定义 trust_score 变量（用于决策矩阵）
    trust_score = user.trust_score

    # 【新增】从 file_operation 中提取 USB写入标记
    file_op_data = data.get('file_operation', {})
    has_usb_write = file_op_data.get('has_usb_write', False)
    has_usb = file_op_data.get('has_usb_file_op', False)
    usb_mount_points = file_op_data.get('usb_mount_points', [])

    # 【新增】根据异常分数和行为类型判断行为风险等级
    if final_anomaly_score > 0.7 or is_sens:
        behavior_risk = 'high'
    elif final_anomaly_score > 0.4:
        behavior_risk = 'medium'
    else:
        behavior_risk = 'low'

    # 【新增】屏幕共享检测 - 仅记录信息，不在此处扣分（避免与交叉决策矩阵重复扣分）
    # 【核心修复】前端传递的是嵌套结构: screen_share: {is_sharing, app_name, sharing_type}
    screen_share_data = data.get('screen_share', {})
    is_screen_sharing = screen_share_data.get('is_sharing', False) or data.get('is_screen_sharing', False)
    screen_share_app = screen_share_data.get('app_name') or data.get('screen_share_app')
    screen_share_type = screen_share_data.get('sharing_type') or data.get('screen_share_type')

    if is_screen_sharing:
        try:
            print(f"📺 [屏幕共享检测] 类型: {screen_share_type}, 应用: {screen_share_app}")
        except OSError:
            print(f"[Screen Sharing Detection] Type: {screen_share_type}, App: {screen_share_app}")

    # ==================================================================================
    # 【核心修改】交叉决策矩阵 — 替代原来只看异常分的一刀切逻辑
    #
    # 矩阵规则：
    #                  🔴 高危             🟡 中危            🟢 低危
    #  <60 (低信任)     block             confirm            静默
    #  60-80 (中信任)   confirm           静默                静默
    #  >80 (高信任)     warn              静默                静默
    # 
    # 【特殊规则】敏感词 + USB写入 → 任何信任分都至少 confirm，低信任直接 block
    # ==================================================================================

    # 【核心增强】敏感词 + USB写入的特殊处理
    if is_sens and has_usb_write:
        if trust_score < 60:
            # 低信任 + 敏感词 + USB写入 = 直接阻断并删除文件
            action_taken = "block"
            alert_level = "critical"
            new_trust_score = max(new_trust_score - 20, 0)  # 大幅扣分
            try:
                print(f"🚫 [矩阵决策] 低信任({trust_score:.1f}) + 敏感词{matched_words} + USB写入 → 阻断并删除文件，信任分-20")
            except OSError:
                print(f"[Matrix Decision] Low trust({trust_score:.1f}) + sensitive words{matched_words} + USB write → Block & delete file, trust score -20")
        elif trust_score < 80:
            # 中信任 + 敏感词 + USB写入 = 二次确认
            action_taken = "confirm_required"
            alert_level = "high"
            new_trust_score = max(new_trust_score - 10, 0)
            try:
                print(f"⚠️ [矩阵决策] 中信任({trust_score:.1f}) + 敏感词{matched_words} + USB写入 → 二次确认，信任分-10")
            except OSError:
                print(f"[Matrix Decision] Medium trust({trust_score:.1f}) + sensitive words{matched_words} + USB write → Secondary confirmation, trust score -10")
        else:
            # 高信任 + 敏感词 + USB写入 = 至少警告
            action_taken = "confirm_required"  # 【升级】即使是高信任也要确认
            alert_level = "high"
            new_trust_score = max(new_trust_score - 5, 0)
            try:
                print(f"📝 [矩阵决策] 高信任({trust_score:.1f}) + 敏感词{matched_words} + USB写入 → 二次确认，信任分-5")
            except OSError:
                print(f"[Matrix Decision] High trust({trust_score:.1f}) + sensitive words{matched_words} + USB write → Secondary confirmation, trust score -5")
    # --- 原有交叉决策矩阵逻辑 ---
    elif trust_score < 60 and behavior_risk == 'high':
        action_taken = "block"
        alert_level = "critical"
        new_trust_score = max(new_trust_score - 15, 0)
        try:
            print(f" [矩阵决策] 低信任({trust_score:.1f}) + 高危行为 → 阻断，信任分-15")
        except OSError:
            # Windows控制台编码问题时的备选方案
            print(f"[Matrix Decision] Low trust({trust_score:.1f}) + High risk behavior → Block, trust score -15")
    elif trust_score < 60 and behavior_risk == 'medium':
        action_taken = "confirm_required"
        alert_level = "high"
        new_trust_score = max(new_trust_score - 10, 0)
        try:
            print(f"⚠️ [矩阵决策] 低信任({trust_score:.1f}) + 中危行为 → 二次确认，信任分-10")
        except OSError:
            # Windows控制台编码问题时的备选方案
            print(f"[Matrix Decision] Low trust({trust_score:.1f}) + Medium risk behavior → Secondary confirmation, trust score -10")
    elif (60 <= trust_score <= 80) and behavior_risk == 'high':
        action_taken = "confirm_required"
        alert_level = "high"
        new_trust_score = max(new_trust_score - 5, 0)
        try:
            print(f"⚠️ [矩阵决策] 中信任({trust_score:.1f}) + 高危行为 → 二次确认，信任分-5")
        except OSError:
            # Windows控制台编码问题时的备选方案
            print(f"[Matrix Decision] Medium trust({trust_score:.1f}) + High risk behavior → Secondary confirmation, trust score -5")
    elif trust_score > 80 and behavior_risk == 'high':
        action_taken = "warn"
        alert_level = "medium"
        new_trust_score = max(new_trust_score - 2, 0)
        try:
            print(f"📝 [矩阵决策] 高信任({trust_score:.1f}) + 高危行为 → 仅告警，信任分-2")
        except OSError:
            # Windows控制台编码问题时的备选方案
            print(f"[Matrix Decision] High trust({trust_score:.1f}) + High risk behavior → Warning only, trust score -2")
    else:
        # 中低风险 + 中高信任 = 静默记录
        action_taken = "pass"
        alert_level = "low"
        try:
            print(f"📝 [矩阵决策] 信任({trust_score:.1f}) + {behavior_risk}风险 → 静默记录")
        except OSError:
            # Windows控制台编码问题时的备选方案
            print(f"[Matrix Decision] Trust({trust_score:.1f}) + {behavior_risk} risk → Silent logging")

    # --- 二次确认特殊处理：返回给Agent弹窗 ---
    if action_taken == "confirm_required":
        # 【修复】根据实际触发原因生成精准的 trigger_reason
        if is_sens and matched_words:
            trigger_reason = 'sensitive_words'
        elif has_usb_write:
            trigger_reason = 'usb_write'
        elif has_usb:
            trigger_reason = 'usb_device'
        elif trust_score < 60:
            trigger_reason = 'low_trust'
        else:
            trigger_reason = 'anomaly_behavior'

        response_data = {
            'status': 'confirm_required',
            'action': 'confirm_required',
            'file_name': action_detail.split(':')[-1].strip() if ':' in action_detail else '未知文件',
            'operation': behavior_type,
            'sensitive_words': matched_words if is_sens else [],
            'trust_score': trust_score,
            'trigger_reason': trigger_reason,
            'message': f'检测到{"敏感词：" + ", ".join(matched_words) if is_sens else "高风险行为"}',
            'log_id': None
        }

        try:
            print(f"🔔 交叉矩阵判定：返回二次确认请求")
        except OSError:
            # Windows控制台编码问题时的备选方案
            print(f"Cross matrix decision: Return secondary confirmation request")

        # 先创建行为日志
        log = BehaviorLog(
            user_id=user.id,
            device_id=device.id,
            behavior_type=behavior_type,
            action_detail=action_detail,
            is_sensitive=is_sens,
            anomaly_score=round(final_anomaly_score, 2),
            ip_address=data.get('ip_address'),
            network_type=data.get('network_type'),
            is_vpn=data.get('is_vpn', False),
            location_hint=data.get('location_hint'),
            is_screen_sharing=data.get('is_screen_sharing', False),
            screen_share_app=data.get('screen_share_app'),
            screen_share_type=data.get('screen_share_type'),
            # 【新增】专用字段落库
            file_op_info=json.dumps(data.get('file_operation', {})),
            email_op_info=json.dumps(data.get('email_operation', {})),
            browser_op_info=json.dumps(data.get('browser_operation', {}))
        )
        db.session.add(log)
        db.session.flush()
        response_data['log_id'] = log.id

        # 更新信任分（临时降低，根据用户决策再调整）
        old_trust_score = user.trust_score
        user.trust_score = max(new_trust_score, 0)
        db.session.commit()

        return jsonify(response_data), 200

    # 更新用户信任分到数据库
    old_trust_score = user.trust_score
    user.trust_score = round(new_trust_score, 2)
    db.session.add(user)  # 【修复】确保SQLAlchemy追踪到信任分变更

    if abs(old_trust_score - new_trust_score) > 0.1:
        try:
            print(f"💾 信任分已更新: {old_trust_score:.2f} → {new_trust_score:.2f}")
        except OSError:
            # Windows控制台编码问题时的备选方案
            print(f"Trust score updated: {old_trust_score:.2f} → {new_trust_score:.2f}")

        # 【新增】记录信任分变更审计日志
        try:
            from services.audit_service import audit_logger
            reason_parts = []
            if is_sens:
                reason_parts.append('敏感词违规')
            if behavior_risk == 'high':
                reason_parts.append('高风险行为')
            elif behavior_risk == 'medium':
                reason_parts.append('中风险行为')

            reason = ', '.join(reason_parts) if reason_parts else '行为基线评估'
            audit_logger.log_trust_score_update(
                user_id=user.id,
                old_score=old_trust_score,
                new_score=new_trust_score,
                reason=reason
            )
        except Exception as e:
            try:
                print(f"⚠️ 审计日志记录失败: {e}")
            except OSError:
                # Windows控制台编码问题时的备选方案
                print(f"Audit log recording failed: {e}")

    # 落库记录 —— 补充基线异常分和上下文数据
    log = BehaviorLog(
        user_id=user.id,
        device_id=device.id,
        behavior_type=behavior_type,
        action_detail=action_detail,
        is_sensitive=is_sens,
        anomaly_score=round(final_anomaly_score, 2),  # 综合异常分
        # 【新增】上下文环境字段
        ip_address=data.get('ip_address'),
        network_type=data.get('network_type'),
        is_vpn=data.get('is_vpn', False),
        location_hint=data.get('location_hint'),
        # 【新增】屏幕共享检测数据
        is_screen_sharing=data.get('is_screen_sharing', False),
        screen_share_app=data.get('screen_share_app'),
        screen_share_type=data.get('screen_share_type'),
        # 【新增】专用字段落库
        file_op_info=json.dumps(data.get('file_operation', {})),
        email_op_info=json.dumps(data.get('email_operation', {})),
        browser_op_info=json.dumps(data.get('browser_operation', {}))
    )
    db.session.add(log)
    db.session.flush()  # 获取 log.id

    # 告警逻辑 —— 【核心修复】只对真正的异常行为创建alerts记录
    # action_taken == "pass" → 不告警（正常行为）
    # action_taken == "warn" → 低风险告警（仅记录，不弹窗）
    # action_taken == "confirm_required" → 中高风险告警（需要用户确认或管理员审批）
    if action_taken != "pass":
        # 【新增】根据实际触发原因生成精准的告警描述
        trigger_reasons = []
        
        # 1. 敏感词检测
        if is_sens and matched_words:
            trigger_reasons.append(f"敏感词违规: {', '.join(matched_words)}")
        
        # 2. USB设备操作
        if has_usb_write:
            trigger_reasons.append("U盘写入文件（数据泄露风险）")
        elif has_usb and usb_mount_points:
            trigger_reasons.append(f"U盘插入: {usb_mount_points}")
        
        # 3. 屏幕共享
        if is_screen_sharing or is_screen_sharing_detected:
            share_type_desc = screen_share_type if screen_share_type else behavior_type
            share_app_desc = screen_share_app if screen_share_app else '未知应用'
            share_desc = f"屏幕共享({share_type_desc}): {share_app_desc}"
            trigger_reasons.append(share_desc)
        
        # 4. 邮件发送
        if is_email_send:
            email_op_data = data.get('email_operation', {})
            send_detail = email_op_data.get('send_detail', '')
            if send_detail:
                trigger_reasons.append(f"邮件发送: {send_detail}")
            else:
                trigger_reasons.append("邮件发送操作")
        
        # 5. 浏览器访问敏感网站
        if is_sensitive_website:
            browser_op_data = data.get('browser_operation', {})
            tab_title = browser_op_data.get('active_tab_title', '')
            if tab_title:
                trigger_reasons.append(f"访问敏感网站: {tab_title}")
            else:
                trigger_reasons.append("访问敏感网站")
        
        # 6. 敏感文件/目录访问
        if is_sensitive_file:
            trigger_reasons.append(f"敏感文件访问: {behavior_type}")
        
        # 7. 行为异常分
        if final_anomaly_score > 85:
            trigger_reasons.append(f"行为异常分{final_anomaly_score:.2f}超过阈值")
        
        # 如果没有具体触发原因，使用默认描述
        if not trigger_reasons:
            trigger_reasons.append(f"{behavior_risk}风险行为 (类型: {behavior_type})")
        
        # 构建详细的告警描述
        discount_desc = ""
        if discount_info['discount_factor'] < 1.0:
            discount_desc = f" [上下文折扣: {discount_info['discount_factor'] * 100:.0f}% ({context_data['location_hint']})]"
        
        description = f"检测到异常行为: {action_detail}. {' | '.join(trigger_reasons)}{discount_desc}"

        alert = Alert(
            user_id=user.id,
            log_id=log.id,
            alert_level=alert_level,
            action_taken=action_taken,
            description=description
        )
        db.session.add(alert)
        db.session.flush()  # 获取 alert.id

        # 【新增】自动触发消息推送（模拟企业微信/邮件/短信）
        try:
            from services.notification_service import notification_service

            # 模拟用户联系方式（实际应从数据库获取）
            user_email = f"{user.work_wechat_id}@company.com"
            phone_number = f"138{user.id:08d}"  # 模拟手机号

            # 根据告警级别发送通知
            push_results = notification_service.send_comprehensive_notification(
                user_name=user.name,
                user_email=user_email,
                phone_number=phone_number,
                alert_level=alert_level,
                description=alert.description,
                action_taken=action_taken
            )

            # 打印推送结果（实际可记录到数据库）
            try:
                print(f"\n✅ 告警 #{alert.id} 推送完成，共发送 {len(push_results)} 条通知")
                for result in push_results:
                    print(f"   - {result['push_type']}: {result['message']}")
            except OSError:
                # Windows控制台编码问题时的备选方案
                print(f"\nAlert #{alert.id} push completed, sent {len(push_results)} notifications")
                for result in push_results:
                    print(f"   - {result['push_type']}: {result['message']}")
        except Exception as e:
            try:
                print(f"\n⚠️ 消息推送失败: {e}")
            except OSError:
                # Windows控制台编码问题时的备选方案
                print(f"\nMessage push failed: {e}")
            # 推送失败不影响主流程

    db.session.commit()

    # 返回值 —— 原有格式，完全保留
    return jsonify({
        "status": "success",
        "action": action_taken,
        "trust_score": user.trust_score
    })


import json
from flask import request, jsonify
from api.behavior import behavior_bp  # reuse behavior blueprint for simplicity


@behavior_bp.route('/report', methods=['POST'])
def handle_report():
    """
    接收前端发来的指标/事件报告，更新分数或记录
    """
    token = request.headers.get('Authorization', '')
    if not token or not token.startswith('Bearer '):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    # 【修复】使用JWT解码token，兼容系统登录逻辑
    req_data = request.json or {}
    record_type = req_data.get('type')

    from core.db import db, User
    import jwt as jwt_lib
    try:
        real_token = token.split(' ')[1]
        # JWT解码获取user_id
        payload = jwt_lib.decode(real_token, 'your-secret-key', algorithms=['HS256'])
        user_id = payload['user_id']
        user = User.query.get(user_id)
    except Exception as e:
        print(f"[Behavior Report] Token解析失败: {e}")
        return jsonify({"status": "error", "message": "Invalid token"}), 401

    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    if record_type == 'events':
        # 如果有高危事件，扣信誉分
        if req_data.get('data', {}).get('severity') == 'high':
            user.trust_score = max(0, user.trust_score - 10)
            db.session.commit()

            # 【新增】记录审计日志（根据操作类型区分系统）
            desc = req_data.get('data', {}).get('description', '未知操作')
            event_type = req_data.get('data', {}).get('event_type', '')

            # 根据事件类型判断属于哪个系统
            if 'file_copy' in event_type or 'git' in event_type.lower() or 'download' in event_type.lower():
                # 源码下载归类到 source_code
                audit_logger.log_oa_access(
                    user_id=user.id,
                    action='git_download',
                    description=desc,
                    status='success'
                )
                from core.db import AuditLog
                latest_log = AuditLog.query.filter_by(user_id=user.id, action='git_download').order_by(
                    AuditLog.id.desc()).first()
                if latest_log:
                    latest_log.log_type = 'source_code'
                    db.session.commit()
                print(f"[Audit] 记录源码下载日志: {desc}")
            else:
                # 其他操作归类到 approval
                audit_logger.log_oa_access(
                    user_id=user.id,
                    action=event_type,
                    description=desc,
                    status='success'
                )
                print(f"[Audit] 记录OA操作日志: {desc}")

    elif record_type == 'environment':
        # 前端环境切换时重设分数
        env_score = req_data.get('data', {}).get('score', 100)
        user.trust_score = env_score
        db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Report received",
        "current_score": user.trust_score
    })
