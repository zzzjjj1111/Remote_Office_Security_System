"""
信任值计算验证脚本
用于测试 40+30+30 权重分配逻辑是否正确实现
"""

import sys
import os

# 添加backend目录到Python路径
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.insert(0, backend_path)

from flask import Flask
from core.db import db, User, Device
from services.trust_score_service import trust_calculator


def create_test_app():
    """创建测试用的Flask应用"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root@127.0.0.1:3306/remote_office_protection_empty'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app


def test_trust_score_calculation():
    """测试信任值计算逻辑"""
    
    app = create_test_app()
    
    with app.app_context():
        print("\n" + "="*80)
        print("🧪 开始测试信任值计算逻辑 (40+30+30 权重分配)")
        print("="*80 + "\n")
        
        # 测试场景1：正常用户 + 健康设备 + 正常行为
        print("📋 测试场景1：正常办公场景")
        print("-" * 80)
        test_normal_user()
        
        print("\n")
        
        # 测试场景2：设备不合规（补丁缺失）
        print("📋 测试场景2：设备补丁缺失场景")
        print("-" * 80)
        test_unpatched_device()
        
        print("\n")
        
        # 测试场景3：异常行为检测
        print("📋 测试场景3：异常行为场景")
        print("-" * 80)
        test_abnormal_behavior()
        
        print("\n")
        
        # 测试场景4：敏感词违规
        print("📋 测试场景4：敏感词违规范景")
        print("-" * 80)
        test_sensitive_violation()
        
        print("\n" + "="*80)
        print("✅ 所有测试场景完成！")
        print("="*80 + "\n")


def test_normal_user():
    """测试正常用户的信任值计算"""
    
    # 查找或创建测试用户
    user = User.query.filter_by(work_wechat_id='test_normal').first()
    if not user:
        user = User(
            work_wechat_id='test_normal',
            name='测试用户-正常',
            department='研发部',
            position='工程师',
            status='active',
            trust_score=100.0
        )
        db.session.add(user)
        db.session.commit()
    
    # 查找或创建设备
    device = Device.query.filter_by(mac_address='00:11:22:33:44:55').first()
    if not device:
        device = Device(
            mac_address='00:11:22:33:44:55',
            os_info='Windows 11 Pro',
            patch_status='已更新',
            antivirus_status='Windows Defender 正常',
            user_id=user.id,
            compliance_status='compliant'
        )
        db.session.add(device)
        db.session.commit()
    
    # 计算信任值
    result = trust_calculator.calculate_trust_score(
        user_id=user.id,
        device_mac=device.mac_address,
        current_behavior={
            'behavior_type': 'user_active',
            'is_sensitive': False,
            'cpu_usage': 25
        },
        context={
            'network_type': 'office',
            'is_vpn': False,
            'location_hint': '公司网络'
        }
    )
    
    # 打印结果
    print(f"用户: {user.name}")
    print(f"设备状态: 补丁{device.patch_status}, 杀毒软件{device.antivirus_status}")
    print(f"\n信任值分解:")
    print(f"  ✓ 身份认证得分: {result['auth_score']:.2f} / 40  (企业微信SSO双因素)")
    print(f"  ✓ 设备健康得分: {result['health_score']:.2f} / 30  (设备完全合规)")
    print(f"  ✓ 行为基线得分: {result['behavior_score']:.2f} / 30  (行为正常)")
    print(f"\n  ➤ 总信任分: {result['total_score']:.2f} / 100")
    print(f"\n预期结果: 总分应在 85-95 之间（正常办公场景）")
    
    if 85 <= result['total_score'] <= 95:
        print("✅ 测试结果符合预期！")
    else:
        print(f"⚠️ 测试结果偏离预期，请检查计算逻辑")


def test_unpatched_device():
    """测试设备不合规场景"""
    
    user = User.query.filter_by(work_wechat_id='test_unpatched').first()
    if not user:
        user = User(
            work_wechat_id='test_unpatched',
            name='测试用户-设备异常',
            department='销售部',
            position='销售专员',
            status='active',
            trust_score=100.0
        )
        db.session.add(user)
        db.session.commit()
    
    device = Device.query.filter_by(mac_address='00:11:22:33:44:66').first()
    if not device:
        device = Device(
            mac_address='00:11:22:33:44:66',
            os_info='Windows 10',
            patch_status='缺失关键补丁(KB5031445)',
            antivirus_status='未安装/未运行',
            user_id=user.id,
            compliance_status='non_compliant'
        )
        db.session.add(device)
        db.session.commit()
    
    result = trust_calculator.calculate_trust_score(
        user_id=user.id,
        device_mac=device.mac_address,
        current_behavior={
            'behavior_type': 'user_active',
            'is_sensitive': False,
            'cpu_usage': 30
        },
        context={
            'network_type': 'home',
            'is_vpn': False,
            'location_hint': '家庭网络'
        }
    )
    
    print(f"用户: {user.name}")
    print(f"设备状态: 补丁{device.patch_status}, 杀毒软件{device.antivirus_status}")
    print(f"\n信任值分解:")
    print(f"  ✓ 身份认证得分: {result['auth_score']:.2f} / 40  (账户正常)")
    print(f"  ⚠ 设备健康得分: {result['health_score']:.2f} / 30  (设备不合规，扣分)")
    print(f"  ✓ 行为基线得分: {result['behavior_score']:.2f} / 30  (行为正常)")
    print(f"\n  ➤ 总信任分: {result['total_score']:.2f} / 100")
    print(f"\n预期结果: 总分应在 55-70 之间（设备不合规导致降分）")
    
    if 55 <= result['total_score'] <= 70:
        print("✅ 测试结果符合预期！设备健康问题正确反映在信任分中")
    else:
        print(f"⚠️ 测试结果偏离预期")


def test_abnormal_behavior():
    """测试异常行为场景"""
    
    user = User.query.filter_by(work_wechat_id='test_abnormal').first()
    if not user:
        user = User(
            work_wechat_id='test_abnormal',
            name='测试用户-异常行为',
            department='行政部',
            position='行政助理',
            status='active',
            trust_score=100.0
        )
        db.session.add(user)
        db.session.commit()
    
    device = Device.query.filter_by(mac_address='00:11:22:33:44:77').first()
    if not device:
        device = Device(
            mac_address='00:11:22:33:44:77',
            os_info='macOS Sonoma 14.2',
            patch_status='已更新',
            antivirus_status='XProtect 正常',
            user_id=user.id,
            compliance_status='compliant'
        )
        db.session.add(device)
        db.session.commit()
    
    result = trust_calculator.calculate_trust_score(
        user_id=user.id,
        device_mac=device.mac_address,
        current_behavior={
            'behavior_type': 'file_copy',
            'is_sensitive': False,
            'cpu_usage': 85  # 高CPU使用率可能表示异常
        },
        context={
            'network_type': 'mobile',
            'is_vpn': False,
            'location_hint': '移动网络/异地'
        }
    )
    
    print(f"用户: {user.name}")
    print(f"设备状态: 补丁{device.patch_status}, 杀毒软件{device.antivirus_status}")
    print(f"行为特征: 文件拷贝操作, CPU使用率85%, 异地移动网络")
    print(f"\n信任值分解:")
    print(f"  ✓ 身份认证得分: {result['auth_score']:.2f} / 40")
    print(f"  ✓ 设备健康得分: {result['health_score']:.2f} / 30")
    print(f"  ⚠ 行为基线得分: {result['behavior_score']:.2f} / 30  (异常行为导致降分)")
    print(f"\n  ➤ 总信任分: {result['total_score']:.2f} / 100")
    print(f"\n预期结果: 行为得分应低于15分（异常行为显著降低信任）")
    
    if result['behavior_score'] < 15:
        print("✅ 测试结果符合预期！异常行为被正确识别并降低信任分")
    else:
        print(f"⚠️ 行为得分偏高，可能需要调整孤立森林模型参数")


def test_sensitive_violation():
    """测试敏感词违规场景"""
    
    user = User.query.filter_by(work_wechat_id='test_sensitive').first()
    if not user:
        user = User(
            work_wechat_id='test_sensitive',
            name='测试用户-敏感违规',
            department='研发部',
            position='高级工程师',
            status='active',
            trust_score=100.0
        )
        db.session.add(user)
        db.session.commit()
    
    device = Device.query.filter_by(mac_address='00:11:22:33:44:88').first()
    if not device:
        device = Device(
            mac_address='00:11:22:33:44:88',
            os_info='Windows 11 Pro',
            patch_status='已更新',
            antivirus_status='Windows Defender 正常',
            user_id=user.id,
            compliance_status='compliant'
        )
        db.session.add(device)
        db.session.commit()
    
    result = trust_calculator.calculate_trust_score(
        user_id=user.id,
        device_mac=device.mac_address,
        current_behavior={
            'behavior_type': 'file_copy',
            'is_sensitive': True,  # 包含敏感词
            'cpu_usage': 20
        },
        context={
            'network_type': 'office',
            'is_vpn': False,
            'location_hint': '公司网络'
        }
    )
    
    print(f"用户: {user.name}")
    print(f"行为特征: 文件拷贝操作，包含敏感词（如'财务报表'）")
    print(f"\n信任值分解:")
    print(f"  ✓ 身份认证得分: {result['auth_score']:.2f} / 40")
    print(f"  ✓ 设备健康得分: {result['health_score']:.2f} / 30")
    print(f"  ⚠ 行为基线得分: {result['behavior_score']:.2f} / 30  (敏感词违规)")
    print(f"\n  ➤ 总信任分: {result['total_score']:.2f} / 100")
    print(f"\n预期结果: 总分应降至30以下（敏感词严重违规）")
    
    if result['total_score'] <= 30:
        print("✅ 测试结果符合预期！敏感词违规触发严厉惩罚")
    else:
        print(f"⚠️ 信任分仍然偏高，敏感词惩罚力度不足")


if __name__ == '__main__':
    try:
        test_trust_score_calculation()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
