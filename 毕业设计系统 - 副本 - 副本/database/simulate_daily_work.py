"""
员工日常工作行为模拟脚本
功能：
1. 定时运行：每天工作时间（9:00-18:30）模拟员工正常办公行为
2. 二次弹窗模拟：当触发敏感词检测时，自动模拟三种操作（确认/取消/上报）
3. 手动运行模式：支持命令行参数手动触发特定行为
"""

import sys
import os
import random
import json
import time
import argparse
from datetime import datetime, timedelta
import requests

# 配置
SERVER_URL = "http://127.0.0.1:5000/api/behavior/upload"
DECISION_URL = "http://127.0.0.1:5000/api/alerts/decision"
MOCK_MAC_ADDRESS = "AA:BB:CC:DD:EE:FF"

# 正常工作行为模板
NORMAL_BEHAVIORS = [
    {
        'behavior_type': 'file_op',
        'action_detail': '读取日常办公表格: /docs/2024_schedule.docx',
        'file_operation': {
            'has_usb_file_op': False,
            'has_sensitive_file_op': False,
            'operation_detail': '读取日常办公表格: /docs/2024_schedule.docx',
            'usb_mount_points': []
        },
        'email_operation': {},
        'browser_operation': {}
    },
    {
        'behavior_type': 'file_op',
        'action_detail': '访问/拉取项目源码: /repos/core_backend/auth.py',
        'file_operation': {
            'has_usb_file_op': False,
            'has_sensitive_file_op': True,
            'operation_detail': '访问/拉取项目源码: /repos/core_backend/auth.py',
            'usb_mount_points': []
        },
        'email_operation': {},
        'browser_operation': {}
    },
    {
        'behavior_type': 'browser_access',
        'action_detail': 'APP:chrome.exe | WINDOW:访问内部Gitlab',
        'file_operation': {},
        'email_operation': {},
        'browser_operation': {
            'is_browser_active': True,
            'browser_name': 'chrome',
            'active_tab_title': '访问内部Gitlab',
            'active_tab_url': 'https://gitlab.company.com'
        }
    },
    {
        'behavior_type': 'email_attachment',
        'action_detail': '发送日常工作周报附件',
        'file_operation': {},
        'email_operation': {
            'email_client_running': True,
            'is_sending_email': True,
            'has_attachment_operation': True,
            'send_detail': '发送日常工作周报附件'
        },
        'browser_operation': {}
    },
    {
        'behavior_type': 'screen_share',
        'action_detail': '开启腾讯会议屏幕共享',
        'file_operation': {},
        'email_operation': {},
        'browser_operation': {},
        'is_screen_sharing': True,
        'screen_share_app': '腾讯会议',
        'screen_share_type': '视频会议'
    }
]

# 触发敏感词的行为（会触发二次确认）
SENSITIVE_BEHAVIORS = [
    {
        'behavior_type': 'file_op',
        'action_detail': '尝试下载敏感文件: 财务报表.xlsx',
        'file_operation': {
            'has_usb_file_op': False,
            'has_sensitive_file_op': True,
            'operation_detail': '尝试下载敏感文件: 财务报表.xlsx',
            'usb_mount_points': []
        },
        'email_operation': {},
        'browser_operation': {}
    },
    {
        'behavior_type': 'file_op',
        'action_detail': 'U盘文件操作: 客户名单.xlsx',
        'file_operation': {
            'has_usb_file_op': True,
            'has_sensitive_file_op': True,
            'operation_detail': 'U盘文件操作: 客户名单.xlsx',
            'usb_mount_points': ['/Volumes/USB']
        },
        'email_operation': {},
        'browser_operation': {}
    },
    {
        'behavior_type': 'email_attachment',
        'action_detail': '尝试通过外部邮箱发送敏感文件: 未公开源码.zip',
        'file_operation': {},
        'email_operation': {
            'email_client_running': True,
            'is_sending_email': True,
            'has_attachment_operation': True,
            'send_detail': '尝试通过外部邮箱发送敏感文件: 未公开源码.zip'
        },
        'browser_operation': {}
    }
]


def get_network_context():
    """生成网络环境上下文"""
    network_types = ['office', 'home', 'vpn']
    weights = [0.7, 0.2, 0.1]  # 70%公司，20%家庭，10%VPN
    network_type = random.choices(network_types, weights=weights)[0]
    
    location_hints = {
        'office': '公司网络',
        'home': '家庭网络',
        'vpn': 'VPN连接'
    }
    
    ip_prefixes = {
        'office': '192.168.1',
        'home': '10.0.0',
        'vpn': '203.0.113'
    }
    
    return {
        'ip_address': f"{ip_prefixes[network_type]}.{random.randint(50, 200)}",
        'network_type': network_type,
        'is_vpn': network_type == 'vpn',
        'location_hint': location_hints[network_type]
    }


def simulate_behavior(user_id, behavior=None, auto_decision=True):
    """
    模拟单次行为上报
    
    Args:
        user_id: 用户ID
        behavior: 行为模板（None则随机选择）
        auto_decision: 是否自动处理二次确认弹窗
    """
    if behavior is None:
        # 80%正常行为，20%敏感行为
        if random.random() < 0.8:
            behavior = random.choice(NORMAL_BEHAVIORS)
        else:
            behavior = random.choice(SENSITIVE_BEHAVIORS)
    
    network_ctx = get_network_context()
    
    payload = {
        "is_frontend_mock": True,
        "mock_user_id": user_id,
        "mac_address": MOCK_MAC_ADDRESS,
        **behavior,
        **network_ctx,
        "timestamp": datetime.now().isoformat()
    }
    
    print(f"\n{'='*60}")
    print(f"📤 用户 {user_id} 上报行为: {behavior['behavior_type']}")
    print(f"   详情: {behavior['action_detail']}")
    print(f"   网络: {network_ctx['location_hint']}")
    print(f"{'='*60}")
    
    try:
        response = requests.post(SERVER_URL, json=payload, timeout=10)
        result = response.json()
        
        print(f"\n📊 服务器响应:")
        print(f"   状态: {result.get('status')}")
        print(f"   操作: {result.get('action', 'pass')}")
        print(f"   信任分: {result.get('trust_score', 'N/A')}")
        
        # 处理二次确认
        if result.get('action') == 'confirm_required' and auto_decision:
            decision = auto_handle_confirmation(result)
            submit_decision(result.get('log_id'), user_id, decision)
        
        return result
    
    except Exception as e:
        print(f"\n❌ 上报失败: {e}")
        return None


def auto_handle_confirmation(server_response):
    """
    自动处理二次确认弹窗
    模拟三种决策：确认操作、取消操作、上报管理员
    """
    log_id = server_response.get('log_id')
    file_name = server_response.get('file_name', '未知文件')
    sensitive_words = server_response.get('sensitive_words', [])
    
    print(f"\n🔔 触发二次确认:")
    print(f"   文件: {file_name}")
    print(f"   敏感词: {', '.join(sensitive_words)}")
    
    # 随机选择决策（可调整概率）
    decisions = ['confirm', 'cancel', 'report_admin']
    weights = [0.6, 0.3, 0.1]  # 60%确认，30%取消，10%上报
    decision = random.choices(decisions, weights=weights)[0]
    
    decision_labels = {
        'confirm': '✅ 确认操作（正常业务）',
        'cancel': '❌ 取消操作（放弃该操作）',
        'report_admin': '⚠️ 上报管理员（可疑行为）'
    }
    
    print(f"   决策: {decision_labels[decision]}")
    return decision


def submit_decision(log_id, user_id, decision):
    """上报用户决策到服务器"""
    if not log_id:
        print("⚠️  log_id 为空，跳过决策上报")
        return
    
    try:
        response = requests.post(
            DECISION_URL,
            json={
                'log_id': log_id,
                'user_id': user_id,
                'decision': decision
            },
            timeout=10
        )
        result = response.json()
        print(f"   决策结果: {result.get('message')}")
        print(f"   当前信任分: {result.get('trust_score')}")
    except Exception as e:
        print(f"   ❌ 决策上报失败: {e}")


def manual_mode(user_id, behavior_type):
    """
    手动运行模式：执行特定行为
    
    Args:
        user_id: 用户ID
        behavior_type: 行为类型 (normal/sensitive/test_usb/test_screen_share)
    """
    behavior_templates = {
        'normal': random.choice(NORMAL_BEHAVIORS),
        'sensitive': random.choice(SENSITIVE_BEHAVIORS),
        'test_usb': {
            'behavior_type': 'file_op',
            'action_detail': 'U盘文件操作: 测试文件.txt',
            'file_operation': {
                'has_usb_file_op': True,
                'has_sensitive_file_op': False,
                'operation_detail': 'U盘文件操作: 测试文件.txt',
                'usb_mount_points': ['/Volumes/USB']
            },
            'email_operation': {},
            'browser_operation': {}
        },
        'test_screen_share': {
            'behavior_type': 'screen_share',
            'action_detail': '启动未经授权的远程桌面软件 (AnyDesk)',
            'file_operation': {},
            'email_operation': {},
            'browser_operation': {},
            'is_screen_sharing': True,
            'screen_share_app': 'AnyDesk',
            'screen_share_type': '远程控制'
        }
    }
    
    behavior = behavior_templates.get(behavior_type, random.choice(NORMAL_BEHAVIORS))
    print(f"\n🎯 手动模式：执行 {behavior_type} 行为")
    simulate_behavior(user_id, behavior, auto_decision=True)


def scheduled_mode(user_ids, interval_minutes=30, duration_hours=8):
    """
    定时运行模式：模拟工作时间内的正常办公行为
    
    Args:
        user_ids: 用户ID列表
        interval_minutes: 上报间隔（分钟）
        duration_hours: 运行时长（小时）
    """
    print(f"\n🕐 定时模式启动:")
    print(f"   参与用户: {user_ids}")
    print(f"   上报间隔: {interval_minutes} 分钟")
    print(f"   运行时长: {duration_hours} 小时")
    print(f"   开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n⏰ 按 Ctrl+C 可随时停止\n")
    
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=duration_hours)
    cycle_count = 0
    
    try:
        while datetime.now() < end_time:
            cycle_count += 1
            print(f"\n{'='*80}")
            print(f"🔄 第 {cycle_count} 轮上报 ({datetime.now().strftime('%H:%M:%S')})")
            print(f"{'='*80}")
            
            # 随机选择 1-3 个用户进行行为上报
            active_users = random.sample(user_ids, min(random.randint(1, 3), len(user_ids)))
            
            for uid in active_users:
                simulate_behavior(uid, auto_decision=True)
                # 每个用户操作间隔 2-5 秒
                time.sleep(random.uniform(2, 5))
            
            # 等待下一轮
            wait_seconds = interval_minutes * 60
            print(f"\n⏳ 等待 {interval_minutes} 分钟后进行下一轮...")
            time.sleep(wait_seconds)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断，定时任务已停止")
        print(f"✅ 共执行 {cycle_count} 轮上报")


def main():
    parser = argparse.ArgumentParser(description='员工日常工作行为模拟脚本')
    parser.add_argument('--mode', type=str, choices=['manual', 'scheduled'], default='scheduled',
                        help='运行模式：manual（手动）/ scheduled（定时）')
    parser.add_argument('--user', type=int, default=1,
                        help='用户ID（手动模式使用）')
    parser.add_argument('--behavior', type=str, choices=['normal', 'sensitive', 'test_usb', 'test_screen_share'],
                        default='normal', help='行为类型（手动模式使用）')
    parser.add_argument('--users', type=str, default='1,2,3,4,5',
                        help='用户ID列表，逗号分隔（定时模式使用）')
    parser.add_argument('--interval', type=int, default=30,
                        help='上报间隔（分钟，定时模式使用）')
    parser.add_argument('--duration', type=int, default=8,
                        help='运行时长（小时，定时模式使用）')
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("🚀 员工日常工作行为模拟脚本")
    print("="*80)
    
    if args.mode == 'manual':
        # 手动模式
        manual_mode(args.user, args.behavior)
    else:
        # 定时模式
        user_ids = [int(x.strip()) for x in args.users.split(',')]
        scheduled_mode(user_ids, args.interval, args.duration)


if __name__ == "__main__":
    main()
