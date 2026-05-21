"""
基于历史行为日志重新计算所有用户的信任分
用途：数据初始化后，根据历史行为数据重新计算每个员工的信任分

流程：
1. 训练孤立森林模型
2. 训练 K-means 岗位基线
3. 遍历所有用户，基于历史行为日志计算信任分
4. 更新数据库
"""

import sys
import os
from datetime import datetime

# 添加backend目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from flask import Flask
from core.config import Config
from core.db import db, User, Device, BehaviorLog
from services.trust_score_service import trust_calculator
from services.ml_service import BehaviorAnalyzer

# 初始化 Flask 应用
def init_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app


def train_models(app):
    """训练孤立森林和 K-means 基线模型"""
    with app.app_context():
        print("\n" + "="*80)
        print(" 步骤 1：训练机器学习模型")
        print("="*80 + "\n")
        
        # 1. 训练孤立森林模型
        print("🔹 正在训练孤立森林模型...")
        analyzer = BehaviorAnalyzer()
        iforest_success = analyzer.train_isolation_forest(include_false_positives=True)
        if iforest_success:
            print("   ✅ 孤立森林训练完成\n")
        else:
            print("   ⚠️  孤立森林训练失败（数据不足）\n")
        
        # 2. 训练 K-means 岗位基线
        print("🔹 正在训练 K-means 岗位基线...")
        kmeans_result = analyzer.train_user_baseline_kmeans()
        if kmeans_result.get('code') == 200:
            print(f"   ✅ K-means 基线训练完成\n")
        else:
            print(f"   ⚠️  K-means 基线训练失败：{kmeans_result.get('msg')}\n")
        
        return analyzer


def recalculate_all_trust_scores(app, analyzer):
    """遍历所有用户，基于历史行为日志重新计算信任分"""
    with app.app_context():
        print("\n" + "="*80)
        print(" 步骤 2：重新计算所有用户信任分")
        print("="*80 + "\n")
        
        # 获取所有活跃用户
        users = User.query.filter_by(status='active').all()
        print(f" 共找到 {len(users)} 个活跃用户\n")
        
        # 统计信息
        stats = {
            'total': len(users),
            'high_trust': 0,    # > 80
            'medium_trust': 0,  # 60-80
            'low_trust': 0,     # < 60
            'updated': 0
        }
        
        # 打印表头
        print(f"{'用户ID':<8} {'姓名':<12} {'部门':<10} {'旧分数':<10} {'新分数':<10} {'变化':<10} {'等级':<10}")
        print("-" * 80)
        
        # 遍历每个用户
        for user in users:
            old_score = user.trust_score
            
            try:
                # 获取用户的历史行为日志
                user_logs = BehaviorLog.query.filter_by(user_id=user.id)\
                    .order_by(BehaviorLog.timestamp.desc())\
                    .limit(100)\
                    .all()
                
                if not user_logs:
                    # 没有行为日志的用户，保持 100 分
                    new_score = 100.0
                else:
                    # 计算该用户的历史平均异常分
                    avg_anomaly = sum(log.anomaly_score for log in user_logs) / len(user_logs)
                    
                    # 使用信任分计算器计算历史行为得分
                    behavior_score = 30.0 * (1.0 - avg_anomaly / 100.0)
                    
                    # 获取用户的设备健康得分
                    device = Device.query.filter_by(user_id=user.id).first()
                    health_score = trust_calculator._calculate_health_score(
                        device.mac_address if device else None
                    )
                    
                    # 身份认证得分（固定）
                    auth_score = trust_calculator._calculate_auth_score(user)
                    
                    # 总分
                    new_score = auth_score + health_score + behavior_score
                    new_score = max(0.0, min(100.0, new_score))
                
                # 更新数据库
                user.trust_score = round(new_score, 2)
                db.session.commit()
                stats['updated'] += 1
                
                # 统计分布
                if new_score > 80:
                    stats['high_trust'] += 1
                    level = "✅ 高信任"
                elif new_score >= 60:
                    stats['medium_trust'] += 1
                    level = "⚠️  中信任"
                else:
                    stats['low_trust'] += 1
                    level = "🚨 低信任"
                
                # 打印变化
                change = new_score - old_score
                change_str = f"{change:+.2f}"
                print(f"{user.id:<8} {user.name:<12} {user.department:<10} {old_score:<10.2f} {new_score:<10.2f} {change_str:<10} {level}")
            
            except Exception as e:
                print(f"❌ 用户 {user.name} 计算失败: {e}")
                db.session.rollback()
        
        print("-" * 80)
        
        # 打印统计信息
        print(f"\n 信任分分布统计：")
        print(f"   总用户数：{stats['total']}")
        print(f"   高信任（>80 分）：{stats['high_trust']} 人")
        print(f"   中信任（60-80 分）：{stats['medium_trust']} 人")
        print(f"   低信任（<60 分）：{stats['low_trust']} 人")
        print(f"   更新成功：{stats['updated']} 人\n")


def main():
    print("\n" + "="*80)
    print(" 基于历史行为日志重新计算信任分")
    print("="*80)
    print(f" 执行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    try:
        # 初始化应用
        app = init_app()
        
        # 步骤 1：训练模型
        analyzer = train_models(app)
        
        # 步骤 2：重新计算所有用户信任分
        recalculate_all_trust_scores(app, analyzer)
        
        print("\n🎉 所有用户信任分重新计算完成！")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
