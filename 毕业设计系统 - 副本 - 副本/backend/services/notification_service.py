"""
消息推送服务
模拟企业微信/邮件/短信通知功能
用于毕业设计演示，实际生产环境应接入真实的企业微信API
"""

import time
from datetime import datetime


class NotificationService:
    """
    消息推送服务（模拟版）
    支持：企业微信、邮件、短信
    """
    
    def __init__(self):
        self.push_history = []  # 推送历史记录
    
    def send_wechat_notification(self, user_name, alert_level, description, action_taken):
        """
        模拟发送企业微信通知
        
        Args:
            user_name: 用户姓名
            alert_level: 告警级别 (low/medium/high/critical)
            description: 告警描述
            action_taken: 采取的动作 (warn/block)
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'push_type': str,
                'timestamp': str
            }
        """
        # 模拟企业微信推送
        level_text = {
            'low': '🟢 低风险',
            'medium': '🟡 中风险',
            'high': '🟠 高风险',
            'critical': '🔴 极高风险'
        }
        
        action_text = {
            'warn': '⚠️ 预警',
            'block': '🚫 阻断'
        }
        
        # 构造消息内容
        message = f"""
【零信任防护系统告警通知】
━━━━━━━━━━━━━━━━
📊 告警级别：{level_text.get(alert_level, '未知')}
👤 相关人员：{user_name}
🎯 处置动作：{action_text.get(action_taken, '记录')}
📝 详情描述：{description}
⏰ 触发时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━
⚡ 系统已自动处置，请关注后续情况。
        """.strip()
        
        # 模拟推送（实际应调用企业微信API）
        try:
            print(f"\n{'='*60}")
            print(f"📨 【模拟企业微信推送】")
            print(f"{'='*60}")
            print(message)
            print(f"{'='*60}\n")
        except OSError:
            # Windows控制台编码问题时的备选方案
            print(f"\n{'='*60}")
            print(f"[WeChat Notification]")
            print(f"{'='*60}")
            print(message)
            print(f"{'='*60}\n")
        
        # 记录推送历史
        push_record = {
            'push_type': 'wechat',
            'user_name': user_name,
            'alert_level': alert_level,
            'action_taken': action_taken,
            'message': message,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'success'
        }
        self.push_history.append(push_record)
        
        return {
            'success': True,
            'message': '企业微信通知发送成功',
            'push_type': 'wechat',
            'timestamp': push_record['timestamp']
        }
    
    def send_email_notification(self, user_email, alert_level, description):
        """
        模拟发送邮件通知
        
        Args:
            user_email: 用户邮箱
            alert_level: 告警级别
            description: 告警描述
        
        Returns:
            dict: 推送结果
        """
        # 模拟邮件推送
        try:
            print(f"\n{'='*60}")
            print(f"📧 【模拟邮件推送】")
            print(f"{'='*60}")
            print(f"收件人：{user_email}")
            print(f"主题：【安全告警】{alert_level.upper()} 级别异常行为通知")
            print(f"内容：{description}")
            print(f"{'='*60}\n")
        except OSError:
            # Windows控制台编码问题时的备选方案
            print(f"\n{'='*60}")
            print(f"[Email Notification]")
            print(f"{'='*60}")
            print(f"To: {user_email}")
            print(f"Subject: [Security Alert] {alert_level.upper()} Level Abnormal Behavior")
            print(f"Content: {description}")
            print(f"{'='*60}\n")
        
        # 记录推送历史
        push_record = {
            'push_type': 'email',
            'user_email': user_email,
            'alert_level': alert_level,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'success'
        }
        self.push_history.append(push_record)
        
        return {
            'success': True,
            'message': '邮件通知发送成功',
            'push_type': 'email',
            'timestamp': push_record['timestamp']
        }
    
    def send_sms_notification(self, phone_number, alert_level):
        """
        模拟发送短信通知（仅用于高风险/极高风险）
        
        Args:
            phone_number: 手机号
            alert_level: 告警级别
        
        Returns:
            dict: 推送结果
        """
        if alert_level not in ['high', 'critical']:
            return {
                'success': False,
                'message': '短信仅用于高风险/极高风险告警',
                'push_type': 'sms'
            }
        
        # 模拟短信推送
        try:
            print(f"\n{'='*60}")
            print(f"📱 【模拟短信推送】")
            print(f"{'='*60}")
            print(f"手机号：{phone_number}")
            print(f"内容：【零信任系统】{alert_level.upper()}级别安全告警，请立即查看！")
            print(f"{'='*60}\n")
        except OSError:
            # Windows控制台编码问题时的备选方案
            print(f"\n{'='*60}")
            print(f"[SMS Notification]")
            print(f"{'='*60}")
            print(f"Phone: {phone_number}")
            print(f"Content: [Zero Trust System] {alert_level.upper()} level security alert, please check immediately!")
            print(f"{'='*60}\n")
        
        # 记录推送历史
        push_record = {
            'push_type': 'sms',
            'phone_number': phone_number,
            'alert_level': alert_level,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'success'
        }
        self.push_history.append(push_record)
        
        return {
            'success': True,
            'message': '短信通知发送成功',
            'push_type': 'sms',
            'timestamp': push_record['timestamp']
        }
    
    def send_comprehensive_notification(self, user_name, user_email, phone_number, 
                                       alert_level, description, action_taken):
        """
        综合推送：根据告警级别选择推送渠道
        
        规则：
        - low: 仅企业微信
        - medium: 企业微信 + 邮件
        - high: 企业微信 + 邮件 + 短信
        - critical: 企业微信 + 邮件 + 短信（多次提醒）
        
        Args:
            user_name: 用户姓名
            user_email: 用户邮箱
            phone_number: 手机号
            alert_level: 告警级别
            description: 告警描述
            action_taken: 处置动作
        
        Returns:
            list: 所有推送结果
        """
        results = []
        
        # 1. 所有级别都发送企业微信
        wechat_result = self.send_wechat_notification(user_name, alert_level, description, action_taken)
        results.append(wechat_result)
        
        # 2. 中风险及以上发送邮件
        if alert_level in ['medium', 'high', 'critical']:
            email_result = self.send_email_notification(user_email, alert_level, description)
            results.append(email_result)
        
        # 3. 高风险及以上发送短信
        if alert_level in ['high', 'critical']:
            sms_result = self.send_sms_notification(phone_number, alert_level)
            results.append(sms_result)
        
        # 4. 极高风险重复推送（模拟紧急通知）
        if alert_level == 'critical':
            try:
                print("\n🚨 极高风险告警，3秒后再次推送短信提醒...")
            except OSError:
                print("\n[CRITICAL ALERT] Resending SMS notification in 3 seconds...")
            time.sleep(3)  # 模拟延迟
            sms_result2 = self.send_sms_notification(phone_number, alert_level)
            results.append(sms_result2)
        
        return results
    
    def get_push_history(self, limit=20):
        """
        获取推送历史
        
        Args:
            limit: 返回条数限制
        
        Returns:
            list: 推送历史记录
        """
        return self.push_history[-limit:]


# 全局推送服务实例
notification_service = NotificationService()
