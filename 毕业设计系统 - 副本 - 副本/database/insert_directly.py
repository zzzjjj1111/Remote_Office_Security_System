import random
import sys
import os
import json
from datetime import datetime, timedelta
import pymysql
from pymysql.constants import CLIENT

# 添加backend目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from flask import Flask
from core.config import Config
from core.db import db, User, Device, BehaviorLog, Alert, AlgorithmConfig, SensitiveWord, FalsePositiveSample, AuditLog, OaAccessLog

# Configuration
NUM_USERS = 250
NUM_DEVICES = 320
NUM_LOGS_PER_USER = 24  # 250 * 24 = 6000 条日志
NUM_ALERTS = 1500

departments = [('研发部', '开发工程师'), ('研发部', '测试工程师'), ('研发部', '架构师'),
               ('销售部', '客户经理'), ('销售部', '销售总监'),
               ('行政部', '行政专员'), ('财务部', '财务专员'),
               ('安全部', '安全工程师'), ('运维部', '运维工程师')]

os_list = ['Windows 10', 'Windows 11 Pro', 'macOS Sonoma 14.2', 'macOS Ventura 13.5', 'Ubuntu 22.04 LTS', 'iOS 17',
           'Android 14']
patch_status_list = ['已更新', '缺失关键补丁', '严重落后', '正常']
av_status_list = ['Windows Defender 正常', 'Tencent PC Manager 正常', '未安装/未运行', '杀毒软件过期', '正常',
                  '卡巴斯基 正常']

behavior_types = ['file_op', 'usb_device', 'screen_share', 'location', 'email_attachment', 'browser_access']

# 【新增】六类行为专用字段生成函数
def generate_file_op_info(b_type, b_detail):
    """生成文件操作 JSON 数据"""
    if b_type == 'file_op':
        has_usb = 'U 盘' in b_detail or '移动硬盘' in b_detail
        has_sensitive = '源码' in b_detail or '财务' in b_detail or '敏感' in b_detail
        return json.dumps({
            'has_usb_file_op': has_usb,
            'has_sensitive_file_op': has_sensitive,
            'operation_detail': b_detail,
            'usb_mount_points': ['/Volumes/USB'] if has_usb else []
        }, ensure_ascii=False)
    return json.dumps({}, ensure_ascii=False)

def generate_email_op_info(b_type, b_detail):
    """生成邮件操作 JSON 数据"""
    if b_type == 'email_attachment':
        is_sending = '发送' in b_detail
        has_attachment = '附件' in b_detail or '.xlsx' in b_detail or '.zip' in b_detail
        return json.dumps({
            'email_client_running': True,
            'is_sending_email': is_sending,
            'has_attachment_operation': has_attachment,
            'send_detail': b_detail
        }, ensure_ascii=False)
    return json.dumps({}, ensure_ascii=False)

def generate_browser_op_info(b_type, b_detail):
    """生成浏览器操作 JSON 数据"""
    if b_type == 'browser_access':
        is_active = random.random() > 0.3
        browser_name = random.choice(['chrome', 'msedge', 'firefox']) if is_active else None
        tab_title = b_detail if is_active else '未知'
        tab_url = f"https://example.com/{random.randint(1000,9999)}" if is_active else '未知'
        return json.dumps({
            'is_browser_active': is_active,
            'browser_name': browser_name,
            'active_tab_title': tab_title,
            'active_tab_url': tab_url
        }, ensure_ascii=False)
    return json.dumps({}, ensure_ascii=False)

action_details = {
    'file_op': ['访问/拉取项目源码: /repos/core_backend/auth.py', '频繁批量下载前端设计资源',
                '读取日常办公表格: /docs/2024_schedule.docx', '访问财务报表.xlsx', '删除系统日志'],
    'usb_device': ['插入未认证的USB设备: Kingston 64GB', '连接公司授权安全U盘', '插入未知手机设备进行充电',
                   '尝试挂载外部移动硬盘'],
    'screen_share': ['开启腾讯会议屏幕共享', '启动未经授权的远程桌面软件 (AnyDesk)', '开启飞书共享屏幕',
                     '使用TeamViewer远控'],
    'location': ['异地登录: IP位于海外', '办公区正常登录', '家庭宽带登录', '咖啡厅公共Wi-Fi登录'],
    'email_attachment': ['发送日常工作周报附件', '尝试通过外部邮箱发送敏感文件: client_list.xlsx',
                         '接收外部邮件带宏附件', '发送绝密源码压缩包'],
    'browser_access': ['访问内部Gitlab', '全天候后台挂机访问论坛', '登录安全控制台', '访问未知的高危钓鱼网站']
}

alert_levels = ['low', 'medium', 'high', 'critical']


def random_date(start, end):
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = random.randrange(int_delta)
    return start + timedelta(seconds=random_second)


start_date = datetime(2025, 12, 23)  # 【修改】日志开始时间
end_date = datetime(2026, 5, 19)      # 【修改】日志结束时间
# 【新增】确保至少有 14 天的数据用于基线训练
min_date_for_baseline = end_date - timedelta(days=20)

# --- 1. 初始化 Flask 应用和数据库 ---
def init_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app

def create_tables_and_clear_data(app):
    with app.app_context():
        print("正在根据模型定义创建/同步数据库表结构...")
        # 强制删除并重新创建所有表，确保表结构与模型一致
        db.drop_all()
        db.create_all()
        print("✅ 数据库表结构已重新创建！")
        
        print("正在清空旧数据...")
        # 按照外键依赖顺序清空数据，避免报错
        tables_to_clear = [
            OaAccessLog, AuditLog, FalsePositiveSample, Alert, 
            BehaviorLog, SensitiveWord, Device, User
        ]
        for table_model in tables_to_clear:
            try:
                table_model.query.delete()
                print(f"  - 已清空 {table_model.__tablename__}")
            except Exception as e:
                print(f"  - 清空 {table_model.__tablename__} 时出错: {e}")
        
        db.session.commit()
        print("✅ 数据库准备就绪！")

print("Connecting to database and initializing models...")
app = init_app()
create_tables_and_clear_data(app)

# --- 2. 使用 pymysql 进行高性能批量数据插入 ---
print("\n开始生成模拟数据 (Raw SQL Mode)...")
conn = pymysql.connect(host='127.0.0.1', user='root', password='root', database='remote_office_protection_empty', charset='utf8mb4')
cursor = conn.cursor()

try:
    # 1. Generate Users - 【修改】初始信任分全为 100
    print("Inserting users...")
    for i in range(1, NUM_USERS + 1):
        dept, pos = random.choice(departments)
        wechat_id = f"user_{i:04d}"
        if i == 1:
            wechat_id = "admin"  # Keep admin
            dept, pos = "安全部", "高级安全工程师"
        name = f"员工{i}"
        status = 'active' if i > 1 else 'active'
        trust_score = 100.0  # 【核心修改】所有员工初始信任分为 100，后续通过 recalculate_trust_scores.py 重新计算
        created_at = random_date(start_date, end_date)
        # 【新增】添加 wechat_userid 字段
        wechat_userid = f"wx_user_{i:04d}" if i > 1 else "wx_admin"
        cursor.execute(
            "INSERT INTO users (id, work_wechat_id, name, department, position, status, trust_score, wechat_userid, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (i, wechat_id, name, dept, pos, status, trust_score, wechat_userid, created_at))
    conn.commit()

    # 2. Generate Devices
    print("Inserting 600 devices...")
    for i in range(1, NUM_DEVICES + 1):
        mac = ':'.join(['{:02X}'.format(random.randint(0x00, 0xff)) for _ in range(6)])
        os_info = random.choice(os_list)
        patch = random.choice(patch_status_list)
        av = random.choice(av_status_list)
        last_login = random_date(datetime(2024, 3, 1), end_date)
        uid = random.randint(1, NUM_USERS)
        # 【新增】添加健康检查相关字段
        last_health_check = random_date(datetime(2024, 3, 20), end_date) if random.random() > 0.1 else None
        compliance_status = random.choice(['compliant', 'warning', 'non_compliant'])
        cursor.execute(
            "INSERT INTO devices (id, mac_address, os_info, patch_status, antivirus_status, last_login_time, user_id, last_health_check, compliance_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (i, mac, os_info, patch, av, last_login, uid, last_health_check, compliance_status))
    conn.commit()

    # 3. Generate Logs - 【修改】每个用户生成行为日志，总计约 6000 条
    print(f"Inserting behavior logs ({NUM_USERS} users x {NUM_LOGS_PER_USER} logs = {NUM_USERS * NUM_LOGS_PER_USER} total)...")
    log_data = []
    log_id = 1
        
    for uid in range(1, NUM_USERS + 1):
        # 【修改】每个用户生成覆盖完整时间段的日志
        for log_idx in range(NUM_LOGS_PER_USER):
            did = random.randint(1, NUM_DEVICES)
            b_type = random.choice(behavior_types)
            b_detail = random.choice(action_details[b_type])
            is_sensitive = random.choice(
                [True, False]) if '源码' in b_detail or '外部' in b_detail or '异地' in b_detail else False
            score = round(random.uniform(0.6, 1.0), 2) if is_sensitive else round(random.uniform(0.0, 0.4), 2)
                
            # 【核心修改】时间范围：2025.12.23 ~ 2026.05.19
            timestamp = random_date(start_date, end_date)
                
            # 生成网络上下文数据
            network_types = ['office', 'home', 'mobile', 'vpn']
            network_type = random.choice(network_types)
            location_hints = {
                'office': '公司网络',
                'home': '家庭网络',
                'mobile': '移动网络/异地',
                'vpn': 'VPN 连接'
            }
            is_vpn = (network_type == 'vpn')
            ip_address = f"192.168.1.{random.randint(100, 200)}" if network_type == 'office' else \
                         f"10.0.0.{random.randint(50, 100)}" if network_type == 'home' else \
                         f"203.0.113.{random.randint(1, 255)}"
                
            # 屏幕共享检测字段
            is_screen_sharing = (b_type == 'screen_share') and random.random() > 0.3
            screen_share_app = random.choice(['腾讯会议', '飞书', '钉钉', 'TeamViewer', 'AnyDesk', None]) if is_screen_sharing else None
            screen_share_type = random.choice(['视频会议', '远程控制', '系统共享', None]) if is_screen_sharing else None
                
            trust_score_val = 100  # 初始都为 100
                
            # 【新增】生成专用字段 JSON
            file_op_info = generate_file_op_info(b_type, b_detail)
            email_op_info = generate_email_op_info(b_type, b_detail)
            browser_op_info = generate_browser_op_info(b_type, b_detail)
                
            log_data.append((log_id, uid, did, b_type, b_detail, is_sensitive, score, trust_score_val, 
                           ip_address, network_type, is_vpn, location_hints[network_type], timestamp, 
                           is_screen_sharing, screen_share_app, screen_share_type,
                           file_op_info, email_op_info, browser_op_info))
            log_id += 1
    
            if len(log_data) == 500:
                cursor.executemany(
                    "INSERT INTO behavior_logs (id, user_id, device_id, behavior_type, action_detail, is_sensitive, anomaly_score, trust_score, ip_address, network_type, is_vpn, location_hint, timestamp, is_screen_sharing, screen_share_app, screen_share_type, file_op_info, email_op_info, browser_op_info) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    log_data)
                log_data = []
                conn.commit()
        
    if log_data:
        cursor.executemany(
            "INSERT INTO behavior_logs (id, user_id, device_id, behavior_type, action_detail, is_sensitive, anomaly_score, trust_score, ip_address, network_type, is_vpn, location_hint, timestamp, is_screen_sharing, screen_share_app, screen_share_type, file_op_info, email_op_info, browser_op_info) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            log_data)
        conn.commit()
        
    total_logs_generated = log_id - 1
    print(f"✅ 插入 {total_logs_generated} 条行为日志（每个用户 {NUM_LOGS_PER_USER} 条，时间范围：2025.12.23 ~ 2026.05.19）")

    # 4. Generate Alerts - 【修改】生成 1500 条告警记录
    print(f"Inserting alerts...")
    alert_data = []
    total_logs = total_logs_generated  # 使用实际生成的日志数量
    for i in range(1, NUM_ALERTS + 1):
        uid = random.randint(1, NUM_USERS)
        lid = random.randint(1, total_logs)
        lvl = random.choice(alert_levels)
        act = 'block' if lvl == 'critical' else 'warn'
        desc = f"系统检测到该设备产生异常评级 {lvl} 行为，防御动作 {act}"
        created = random_date(start_date, end_date)
        # 【新增】误判反馈字段
        is_false_positive = random.random() > 0.85  # 15%的概率标记为误判
        feedback_type = 'false_positive' if is_false_positive else ('confirmed' if random.random() > 0.5 else 'pending')
        feedback_time = random_date(created, end_date) if is_false_positive else None
        feedback_reason = random.choice([
            '正常业务操作被误判',
            '授权的外部访问',
            '测试环境行为',
            '基线配置不合理',
            None
        ]) if is_false_positive else None
        feedback_admin_id = random.randint(1, 10) if is_false_positive else None  # 前10个用户作为管理员
        baseline_corrected = random.choice([True, False]) if is_false_positive else False
        correction_time = random_date(feedback_time, end_date) if baseline_corrected and feedback_time else None
        # 【新增】信任分扣分数值（模拟扣分：2-20分）
        trust_score_deducted = round(random.uniform(2.0, 20.0), 2) if lvl in ['high', 'critical'] else round(random.uniform(0.5, 5.0), 2)
        
        alert_data.append((uid, lid, lvl, act, desc, created, is_false_positive, feedback_type, feedback_time, feedback_reason, feedback_admin_id, baseline_corrected, correction_time, trust_score_deducted))

    cursor.executemany(
        "INSERT INTO alerts (user_id, log_id, alert_level, action_taken, description, created_at, is_false_positive, feedback_type, feedback_time, feedback_reason, feedback_admin_id, baseline_corrected, correction_time, trust_score_deducted) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        alert_data)
    conn.commit()

    print("Massive dataset successfully inserted directly to database!")

    # 5. Generate False Positive Samples (误判样本记录表)
    print("Inserting false positive samples...")
    cursor.execute("SELECT id FROM alerts WHERE is_false_positive = TRUE")
    false_positive_alerts = cursor.fetchall()
    
    if false_positive_alerts:
        fp_data = []
        for alert_row in false_positive_alerts:
            alert_id = alert_row[0]
            # 获取该告警的详细信息
            cursor.execute("SELECT user_id, log_id FROM alerts WHERE id = %s", (alert_id,))
            alert_info = cursor.fetchone()
            if alert_info:
                uid, lid = alert_info
                # 获取行为日志信息
                cursor.execute("SELECT behavior_type, anomaly_score, device_id FROM behavior_logs WHERE id = %s", (lid,))
                log_info = cursor.fetchone()
                if log_info:
                    behavior_type, anomaly_score, device_id = log_info
                    created = random_date(datetime(2024, 1, 1), end_date)
                    used_for_training = random.choice([True, False])
                    training_time = random_date(created, end_date) if used_for_training else None
                    
                    fp_data.append((alert_id, uid, device_id, behavior_type, anomaly_score, 
                                   '正常业务操作被误判', created, used_for_training, training_time))
        
        if fp_data:
            cursor.executemany(
                "INSERT INTO false_positive_samples (alert_id, user_id, device_id, behavior_type, anomaly_score, feedback_reason, created_at, used_for_training, training_time) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                fp_data)
            conn.commit()
            print(f"✅ 插入 {len(fp_data)} 条误判样本记录")
    else:
        print("️ 没有误判告警，跳过误判样本表")

    # 6. Generate Audit Logs (审计日志表) - 按 OA 系统分类
    print("Inserting audit logs by OA system categories...")
    
    # 【新增】时间范围：最近 7-10 天
    recent_end = datetime.now()
    recent_start = recent_end - timedelta(days=10)
    
    # 定义各系统的操作类型 (key 必须对应 db.py 中 AuditLog.log_type 的枚举值)
    system_configs = {
        'oa_access': {  # 对应协同审批、财务报销等 OA 业务
            'actions': [
                ('submit_approval', '提交审批流程', 'success'),
                ('view_approval', '查看审批详情', 'success'),
                ('urgent_approval', '审批加急操作', 'success'),
                ('approval_blocked', '低信任分尝试加急审批', 'warning'),  # 违规
                ('after_hours_approval', '非工作时间提交审批', 'warning'),  # 违规
                ('submit_expense', '提交报销申请', 'success'),
                ('sensitive_finance_access', '访问敏感财务文件: 薪资数据.xlsx', 'warning'),  # 违规
            ],
            'count': 550
        },
        'system': {  # 对应内部源码仓库、文件共享等系统级操作
            'actions': [
                ('git_download', 'Git 克隆/下载源码', 'success'),
                ('file_share_browse', '文件共享浏览', 'success'),
                ('batch_export', '批量文件导出', 'success'),
                ('sensitive_file_access', '尝试下载敏感文件: 财务报表.xlsx', 'warning'),  # 违规
                ('low_trust_download', '低信任分尝试下载源码', 'warning'),  # 违规
                ('after_hours_download', '非工作时间下载源码', 'warning'),  # 违规
            ],
            'count': 350
        },
        'auth': {  # 登录认证
            'actions': [
                ('login', '用户登录成功', 'success'),
                ('logout', '用户退出登录', 'success'),
                ('login_failed', '密码错误登录失败', 'failure'),
                ('异地登录', '异地 IP 登录失败', 'failure'),
                ('token_refresh', 'Token 刷新成功', 'success'),
            ],
            'count': 400
        },
        'behavior': {  # 行为监控
            'actions': [
                ('health_check', '设备健康检查', 'success'),
                ('antivirus_update', '杀毒软件状态更新', 'success'),
                ('patch_check', '系统补丁检查', 'success'),
                ('screen_share_detected', '检测到屏幕共享: 腾讯会议', 'warning'),
                ('usb_insert', '插入未认证 USB 设备', 'warning'),
                ('file_copy_usb', '文件拷贝到 U 盘', 'warning'),
            ],
            'count': 400
        },
        'device': {  # 设备管理
            'actions': [
                ('device_register', '新设备注册', 'success'),
                ('compliance_check', '设备合规性检查', 'success'),
                ('device_offline', '设备离线', 'warning'),
                ('device_online', '设备重新上线', 'success'),
                ('health_compliance_failed', '健康检查不合规', 'warning'),
            ],
            'count': 300
        }
    }
    
    audit_data = []
    total_count = 0
    
    for system_type, config in system_configs.items():
        actions = config['actions']
        count = config['count']
        
        for i in range(count):
            action, description, status = random.choice(actions)
            uid = random.randint(1, min(NUM_USERS, 100))  # 使用前 100 个用户
            did = random.randint(1, NUM_DEVICES) if random.random() > 0.3 else None
            # 【修改】根据系统类型设置对应的module名称（统一大写）
            module_map = {
                'oa_access': 'OA_ACCESS',
                'system': 'SYSTEM',
                'auth': 'AUTH',
                'behavior': 'BEHAVIOR',
                'device': 'HEALTH'
            }
            module = module_map.get(system_type, system_type.upper())
            
            # 生成 IP 地址
            ip_address = f"192.168.1.{random.randint(100, 200)}"
            
            # 生成 User-Agent
            user_agent = random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Mozilla/5.0 (X11; Linux x86_64)'
            ])
            
            request_method = 'POST' if 'submit' in action or 'upload' in action else 'GET'
            request_path = f"/api/{system_type}/{action}"
            error_message = None if status == 'success' else '操作失败：权限不足或安全风险'
            
            # 生成时间（最近 10 天内）
            created = random_date(recent_start, recent_end)
            
            audit_data.append((system_type, uid, did, action, module, description, ip_address, 
                              user_agent, request_method, request_path, status, error_message,
                              None, None, created))
            total_count += 1
            
            # 批量插入
            if len(audit_data) == 500:
                cursor.executemany(
                    "INSERT INTO audit_logs (log_type, user_id, device_id, action, module, description, ip_address, user_agent, request_method, request_path, status, error_message, old_value, new_value, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    audit_data)
                audit_data = []
                conn.commit()
    
    # 插入剩余数据
    if audit_data:
        cursor.executemany(
            "INSERT INTO audit_logs (log_type, user_id, device_id, action, module, description, ip_address, user_agent, request_method, request_path, status, error_message, old_value, new_value, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            audit_data)
        conn.commit()
    
    print(f"✅ 插入 {total_count} 条审计日志记录（按系统分类）")
    print(f"   - OA业务操作 (oa_access): 550 条")
    print(f"   - 系统级操作 (system): 350 条")
    print(f"   - 登录认证 (auth): 400 条")
    print(f"   - 行为监控: 400 条")
    print(f"   - 设备管理: 300 条")

    # 7. Generate OA Access Logs (OA访问日志表)
    print("Inserting OA access logs...")
    oa_operate_types = ['login_check', 'access_page', 'function_call', 'permission_denied']
    oa_results = ['success', 'fail']
    
    oa_data = []
    for i in range(1, 1001):  # 插入1000条OA访问日志
        uid = random.randint(1, NUM_USERS)
        cursor.execute("SELECT name FROM users WHERE id = %s", (uid,))
        user_result = cursor.fetchone()
        username = user_result[0] if user_result else f"员工{uid}"
        
        operate_type = random.choice(oa_operate_types)
        operate_desc = {
            'login_check': 'OA系统登录验证',
            'access_page': '访问审批流程页面',
            'function_call': '调用报销接口',
            'permission_denied': '越权访问被拒绝'
        }.get(operate_type, '未知操作')
        
        client_ip = f"10.0.0.{random.randint(50, 150)}"
        result = 'success' if operate_type != 'permission_denied' else 'fail'
        created = random_date(datetime(2023, 11, 1), end_date)
        
        oa_data.append((uid, username, operate_type, operate_desc, client_ip, result, created))
        
        if len(oa_data) == 500:
            cursor.executemany(
                "INSERT INTO oa_access_log (user_id, username, operate_type, operate_desc, client_ip, result, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                oa_data)
            oa_data = []
            conn.commit()
    
    if oa_data:
        cursor.executemany(
            "INSERT INTO oa_access_log (user_id, username, operate_type, operate_desc, client_ip, result, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            oa_data)
        conn.commit()
    print(f"✅ 插入 1000 条OA访问日志记录")

    # -------------------------- 新增：初始化算法参数 --------------------------
    # 若表中无数据，则插入默认参数（60分阈值、0.5权重、工作时间配置）
    cursor.execute("SELECT COUNT(*) FROM algorithm_config")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO algorithm_config (trust_threshold, wma_weight, baseline_data, wma_window, k_clusters, work_start_time, work_end_time) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (60, 0.5, '{"clusters": []}', 14, 5, '09:30', '18:30')
        )
        conn.commit()
        print("✅ 算法参数初始化完成（阈值60，权重0.5，工作时间09:30-18:30）")

    # -------------------------- 新增：初始化默认敏感词 --------------------------
    # 获取管理员用户ID（admin）
    cursor.execute("SELECT id FROM users WHERE work_wechat_id = 'admin'")
    admin_result = cursor.fetchone()
    if admin_result:
        admin_id = admin_result[0]
        # 若敏感词表为空，则插入页面默认的两个敏感词
        cursor.execute("SELECT COUNT(*) FROM sensitive_words")
        if cursor.fetchone()[0] == 0:
            now = datetime.now()
            cursor.execute(
                "INSERT INTO sensitive_words (word, risk_level, creator_id, created_at) VALUES (%s, %s, %s, %s), (%s, %s, %s, %s), (%s, %s, %s, %s), (%s, %s, %s, %s)",
                (
                    "财务报表", "高风险", admin_id, now,
                    "未公开源码", "绝密", admin_id, now,
                    "客户名单", "高风险", admin_id, now,
                    "薪资数据", "绝密", admin_id, now
                )
            )
            conn.commit()
            print("✅ 敏感词库初始化完成（4个敏感词）")
    
    print("\n🎉 所有数据初始化完成！")
    print(f" 数据统计：")
    print(f"   - 用户: {NUM_USERS} 条（初始信任分均为 100 分）")
    print(f"   - 设备: {NUM_DEVICES} 条")
    print(f"   - 行为日志: {total_logs_generated} 条（每个用户 {NUM_LOGS_PER_USER} 条）")
    print(f"   - 告警记录: {NUM_ALERTS} 条")
    print(f"   - 误判样本: {len(false_positive_alerts) if false_positive_alerts else 0} 条")
    print(f"   - 审计日志: {total_count} 条（按OA系统分类）")
    print(f"   - OA访问日志: 1000 条")
    print(f"   - 算法配置: 1 条")
    print(f"   - 敏感词: 4 条")
    print(f"\n💡 下一步：运行 recalculate_trust_scores.py 重新计算员工信任分")
    print(f"   - 预计结果：约30人低分(<60)，80人中分(60-70)，剩余高分(>70)")

finally:
    cursor.close()
    conn.close()