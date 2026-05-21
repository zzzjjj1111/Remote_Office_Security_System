"""
终端健康基线检查服务
功能：
1. 根据补丁状态和杀毒状态判断设备合规性
2. 自动更新设备合规状态
3. 生成合规/不合规告警
"""
from datetime import datetime
from core.db import db, Device, Alert, User


class TerminalHealthChecker:
    """终端健康检查器"""
    
    # 合规判定规则
    COMPLIANCE_RULES = {
        # 补丁状态规则
        'patch': {
            '已更新': {'status': 'compliant', 'score': 0},
            '缺失关键补丁': {'status': 'warning', 'score': -10},
            '严重落后': {'status': 'non_compliant', 'score': -30},
            '未知': {'status': 'warning', 'score': -5}
        },
        # 杀毒软件状态规则
        'antivirus': {
            '正常': {'status': 'compliant', 'score': 0},
            '过期': {'status': 'warning', 'score': -15},
            '未安装/未运行': {'status': 'non_compliant', 'score': -25},
            '未知': {'status': 'warning', 'score': -5}
        }
    }
    
    @staticmethod
    def check_device_health(mac_address, patch_status, antivirus_status, user_id=None):
        """
        检查设备健康状态
        
        Args:
            mac_address: 设备MAC地址
            patch_status: 补丁状态
            antivirus_status: 杀毒软件状态
            user_id: 用户ID
            
        Returns:
            dict: {
                'compliance_status': 'compliant/warning/non_compliant',
                'risk_score': int,  # 风险分数（负值表示风险）
                'issues': list,  # 问题列表
                'device_id': int
            }
        """
        try:
            # 1. 查找或创建设备记录
            device = Device.query.filter_by(mac_address=mac_address).first()
            if not device:
                device = Device(
                    mac_address=mac_address,
                    user_id=user_id,
                    os_info="Unknown"
                )
                db.session.add(device)
                db.session.flush()  # 获取device.id但不提交
            
            # 2. 更新设备健康信息
            device.patch_status = patch_status
            device.antivirus_status = antivirus_status
            device.last_health_check = datetime.now()
            device.last_login_time = datetime.now()
            
            # 3. 合规性判定
            issues = []
            total_risk_score = 0
            worst_status = 'compliant'
            
            # 检查补丁状态
            patch_rule = TerminalHealthChecker.COMPLIANCE_RULES['patch'].get(patch_status, {'status': 'warning', 'score': -5})
            total_risk_score += patch_rule['score']
            if patch_rule['status'] != 'compliant':
                issues.append(f"补丁状态：{patch_status}")
                if patch_rule['status'] == 'non_compliant':
                    worst_status = 'non_compliant'
                elif worst_status != 'non_compliant':
                    worst_status = 'warning'
            
            # 检查杀毒软件状态
            # 简化匹配：检查字符串是否包含关键词
            av_status_simplified = '未知'
            if '正常' in antivirus_status:
                av_status_simplified = '正常'
            elif '过期' in antivirus_status:
                av_status_simplified = '过期'
            elif '未安装' in antivirus_status or '未运行' in antivirus_status:
                av_status_simplified = '未安装/未运行'
            
            av_rule = TerminalHealthChecker.COMPLIANCE_RULES['antivirus'].get(av_status_simplified, {'status': 'warning', 'score': -5})
            total_risk_score += av_rule['score']
            if av_rule['status'] != 'compliant':
                issues.append(f"杀毒软件：{antivirus_status}")
                if av_rule['status'] == 'non_compliant':
                    worst_status = 'non_compliant'
                elif worst_status != 'non_compliant':
                    worst_status = 'warning'

            # 4. 【核心修复】检查健康状态是否发生变化（防止告警风暴）
            # 如果上一次状态和当前状态一样，就不再重复生成告警！
            status_changed = (device.compliance_status != worst_status)
            device.compliance_status = worst_status

            # 5. 只有存在不合规问题，【且状态发生恶化/变化时】，才生成告警
            if worst_status != 'compliant' and user_id and status_changed:
                alert_level = 'high' if worst_status == 'non_compliant' else 'medium'
                action_taken = 'block' if worst_status == 'non_compliant' else 'warn'
                
                description = f"终端健康检查异常：{', '.join(issues)} | 风险评分：{total_risk_score}"
                
                # 创建行为日志记录
                from core.db import BehaviorLog
                behavior_log = BehaviorLog(
                    user_id=user_id,
                    device_id=device.id,
                    behavior_type='health_check',
                    action_detail=description,
                    is_sensitive=False,
                    anomaly_score=abs(total_risk_score) / 30.0,  # 归一化到0-1
                    trust_score=100 + total_risk_score,
                    timestamp=datetime.now()
                )
                db.session.add(behavior_log)
                db.session.flush()
                
                # 创建告警记录
                alert = Alert(
                    user_id=user_id,
                    log_id=behavior_log.id,
                    alert_level=alert_level,
                    action_taken=action_taken,
                    description=description,
                    created_at=datetime.now()
                )
                db.session.add(alert)
            
            db.session.commit()
            
            return {
                'code': 200,
                'compliance_status': worst_status,
                'risk_score': total_risk_score,
                'issues': issues,
                'device_id': device.id,
                'device': device
            }
            
        except Exception as e:
            db.session.rollback()
            print(f"[Health Check] Error: {e}")
            return {
                'code': 500,
                'msg': f'健康检查失败：{str(e)}'
            }
    
    @staticmethod
    def get_compliance_stats():
        """
        获取整体合规统计
        
        Returns:
            dict: 合规统计数据
        """
        try:
            total_devices = Device.query.count()
            compliant_devices = Device.query.filter_by(compliance_status='compliant').count()
            warning_devices = Device.query.filter_by(compliance_status='warning').count()
            non_compliant_devices = Device.query.filter_by(compliance_status='non_compliant').count()
            
            compliance_rate = (compliant_devices / total_devices * 100) if total_devices > 0 else 0
            
            # 获取不合规设备列表
            non_compliant_list = []
            non_compliant_devices_query = Device.query.filter(
                Device.compliance_status != 'compliant'
            ).limit(20).all()
            
            for device in non_compliant_devices_query:
                user = User.query.get(device.user_id) if device.user_id else None
                non_compliant_list.append({
                    'device_id': device.id,
                    'mac_address': device.mac_address,
                    'os_info': device.os_info,
                    'patch_status': device.patch_status,
                    'antivirus_status': device.antivirus_status,
                    'compliance_status': device.compliance_status,
                    'last_health_check': device.last_health_check.strftime('%Y-%m-%d %H:%M:%S') if device.last_health_check else '从未检查',
                    'user_name': user.name if user else '未知',
                    'user_id': user.id if user else None
                })
            
            return {
                'code': 200,
                'data': {
                    'total_devices': total_devices,
                    'compliant_devices': compliant_devices,
                    'warning_devices': warning_devices,
                    'non_compliant_devices': non_compliant_devices,
                    'compliance_rate': round(compliance_rate, 2),
                    'non_compliant_list': non_compliant_list
                }
            }
        except Exception as e:
            return {
                'code': 500,
                'msg': f'获取合规统计失败：{str(e)}'
            }
