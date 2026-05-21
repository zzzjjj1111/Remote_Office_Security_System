"""
动态信任值计算服务
按照设计文档要求实现 40+30+30 权重分配：
- 身份认证得分：40分
- 设备健康得分：30分  
- 行为基线匹配度：30分
"""

import sys
import os
# 添加backend目录到Python路径，确保能正确导入core模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.db import db, User, Device, BehaviorLog
from services.ml_service import BehaviorAnalyzer
from services.health_check_service import TerminalHealthChecker
import json


class TrustScoreCalculator:
    """
    信任值计算器
    严格按照 40+30+30 权重分配计算用户信任分
    """
    
    def __init__(self):
        self.analyzer = BehaviorAnalyzer()
    
    def calculate_trust_score(self, user_id, device_mac=None, current_behavior=None, context=None):
        """
        计算用户当前信任值
        
        Args:
            user_id: 用户ID
            device_mac: 设备MAC地址（可选）
            current_behavior: 当前行为数据字典（可选）
            context: 上下文环境数据（可选）
        
        Returns:
            dict: {
                'total_score': float,  # 总信任分 (0-100)
                'auth_score': float,   # 身份认证得分 (0-40)
                'health_score': float, # 设备健康得分 (0-30)
                'behavior_score': float, # 行为基线得分 (0-30)
                'details': dict  # 详细评分说明
            }
        """
        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"用户 {user_id} 不存在")
        
        # 1. 身份认证得分（40分）
        auth_score = self._calculate_auth_score(user)
        
        # 2. 设备健康得分（30分）
        health_score = self._calculate_health_score(device_mac)
        
        # 3. 行为基线匹配度得分（30分）
        behavior_score = self._calculate_behavior_score(user_id, current_behavior, context)
        
        # 4. 计算总分
        total_score = auth_score + health_score + behavior_score
        
        # 5. 限制在 0-100 区间
        total_score = max(0.0, min(100.0, total_score))
        
        result = {
            'total_score': round(total_score, 2),
            'auth_score': round(auth_score, 2),
            'health_score': round(health_score, 2),
            'behavior_score': round(behavior_score, 2),
            'details': {
                'user_status': user.status,
                'auth_method': '企业微信SSO' if user.work_wechat_id else '账号密码',
                'device_compliance': self._get_device_compliance(device_mac),
                'behavior_anomaly': self._get_behavior_anomaly_info(user_id, current_behavior, context)
            }
        }
        
        return result
    
    def _calculate_auth_score(self, user):
        """
        计算身份认证得分（满分40分）
        
        评分规则：
        - 账户状态正常：+30分
        - 使用企业微信SSO双因素认证：+10分
        - 仅账号密码认证：+5分
        - 账户被封锁：0分
        """
        score = 0.0
        
        # 基础分：账户状态
        if user.status == 'active':
            score += 30.0
        elif user.status == 'blocked':
            return 0.0  # 被封锁的账户直接0分
        
        # 认证方式加分
        if user.work_wechat_id:
            # 企业微信SSO（模拟双因素认证）
            score += 10.0
        else:
            # 普通账号密码
            score += 5.0
        
        return min(40.0, score)
    
    def _calculate_health_score(self, device_mac):
        """
        计算设备健康得分（满分30分）
        
        评分规则：
        - 补丁状态：已更新(+15)、缺失关键补丁(+8)、严重落后(+0)
        - 杀毒软件：正常运行(+15)、过期(+5)、未安装(+0)
        """
        if not device_mac:
            return 15.0  # 没有设备信息时给中等分数
        
        device = Device.query.filter_by(mac_address=device_mac).first()
        if not device:
            return 15.0  # 设备不存在时给中等分数
        
        score = 0.0
        
        # 1. 补丁状态评分（15分）
        patch_status = device.patch_status or '未知'
        if '已更新' in patch_status:
            score += 15.0
        elif '缺失' in patch_status or 'warning' in str(device.compliance_status or '').lower():
            score += 8.0
        elif '严重落后' in patch_status or 'non_compliant' in str(device.compliance_status or '').lower():
            score += 0.0
        else:
            score += 8.0  # 未知状态给中等分
        
        # 2. 杀毒软件评分（15分）
        antivirus_status = device.antivirus_status or '未知'
        if '正常' in antivirus_status or 'active' in antivirus_status.lower():
            score += 15.0
        elif '过期' in antivirus_status or 'expired' in antivirus_status.lower():
            score += 5.0
        elif '未安装' in antivirus_status or '未运行' in antivirus_status or 'none' in antivirus_status.lower():
            score += 0.0
        else:
            score += 5.0  # 未知状态给低分
        
        return min(30.0, score)
    
    def _calculate_behavior_score(self, user_id, current_behavior=None, context=None):
        """
        计算行为基线匹配度得分（满分30分）
        
        评分规则：
        - 基于孤立森林异常分和双基线异常分综合计算
        - 异常分越低，得分越高
        - 公式：behavior_score = 30 * (1 - anomaly_score/100)
        """
        if not current_behavior:
            # 没有当前行为数据时，返回历史平均行为得分
            return self._get_historical_behavior_score(user_id)
        
        try:
            # 提取当前行为特征
            from services.ml_service import BehaviorAnalyzer
            analyzer = BehaviorAnalyzer()
            
            # 构造临时 BehaviorLog 用于特征提取
            temp_log = BehaviorLog(
                user_id=user_id,
                behavior_type=current_behavior.get('behavior_type', 'unknown'),
                is_sensitive=current_behavior.get('is_sensitive', False)
            )
            
            current_features = analyzer.extract_behavior_features([temp_log])
            
            # 获取孤立森林异常分 (0-100)
            isolate_anomaly_score = analyzer.get_isolation_forest_score(current_features)
            
            # 获取双基线异常分 (0-100)，应用上下文折扣
            baseline_result = analyzer.detect_anomaly_by_baseline(
                user_id, 
                current_features, 
                context=context
            )
            baseline_anomaly_score = baseline_result['final_score'] * 100
            
            # 综合异常分：孤立森林(50%) + 双基线(50%)
            final_anomaly_score = (isolate_anomaly_score + baseline_anomaly_score) / 2
            
            # 转换为得分：异常分越低，得分越高
            behavior_score = 30.0 * (1.0 - final_anomaly_score / 100.0)
            
            return max(0.0, min(30.0, behavior_score))
        
        except Exception as e:
            print(f"[Trust Calculator] 行为得分计算异常: {e}")
            return 15.0  # 异常时返回中等分数
    
    def _get_historical_behavior_score(self, user_id):
        """
        获取用户历史行为的平均得分
        当没有实时行为数据时使用
        """
        try:
            # 查询最近10条行为日志的平均异常分
            recent_logs = BehaviorLog.query.filter_by(user_id=user_id)\
                .order_by(BehaviorLog.timestamp.desc())\
                .limit(10)\
                .all()
            
            if not recent_logs:
                return 25.0  # 新用户默认较高分
            
            avg_anomaly = sum(log.anomaly_score for log in recent_logs) / len(recent_logs)
            behavior_score = 30.0 * (1.0 - avg_anomaly / 100.0)
            
            return max(0.0, min(30.0, behavior_score))
        
        except Exception as e:
            print(f"[Trust Calculator] 历史行为得分计算异常: {e}")
            return 20.0
    
    def _get_device_compliance(self, device_mac):
        """获取设备合规状态描述"""
        if not device_mac:
            return "未绑定设备"
        
        device = Device.query.filter_by(mac_address=device_mac).first()
        if not device:
            return "设备不存在"
        
        return {
            'patch_status': device.patch_status or '未知',
            'antivirus_status': device.antivirus_status or '未知',
            'compliance_status': device.compliance_status or 'unknown'
        }
    
    def _get_behavior_anomaly_info(self, user_id, current_behavior, context):
        """获取行为异常详细信息"""
        if not current_behavior:
            return {'message': '无实时行为数据'}
        
        try:
            from services.ml_service import BehaviorAnalyzer
            analyzer = BehaviorAnalyzer()
            
            temp_log = BehaviorLog(
                user_id=user_id,
                behavior_type=current_behavior.get('behavior_type', 'unknown'),
                is_sensitive=current_behavior.get('is_sensitive', False)
            )
            
            current_features = analyzer.extract_behavior_features([temp_log])
            isolate_score = analyzer.get_isolation_forest_score(current_features)
            
            baseline_result = analyzer.detect_anomaly_by_baseline(
                user_id, 
                current_features, 
                context=context
            )
            
            return {
                'isolation_forest_score': round(isolate_score, 2),
                'baseline_raw_score': round(baseline_result['raw_score'] * 100, 2),
                'baseline_discount_factor': round(baseline_result['discount_factor'], 2),
                'baseline_final_score': round(baseline_result['final_score'] * 100, 2),
                'context': context or {}
            }
        except Exception as e:
            return {'error': str(e)}
    
    def update_user_trust_score(self, user_id, new_score):
        """
        更新用户信任分到数据库
        
        Args:
            user_id: 用户ID
            new_score: 新的信任分值
        """
        user = User.query.get(user_id)
        if user:
            old_score = user.trust_score
            user.trust_score = round(new_score, 2)
            db.session.commit()
            try:
                print(f"[Trust Update] 用户 {user.name} 信任分: {old_score:.2f} → {new_score:.2f}")
            except OSError:
                # Windows控制台编码问题时的备选方案
                print(f"[Trust Update] User {user.id} trust score: {old_score:.2f} -> {new_score:.2f}")


# 全局单例
trust_calculator = TrustScoreCalculator()
