from flask import Blueprint, jsonify
from core.db import db, AlgorithmConfig, User
from services.ml_service import BehaviorAnalyzer
import json

# 蓝图注册
baseline_bp = Blueprint('baseline', __name__)
analyzer = BehaviorAnalyzer()


@baseline_bp.route('/rebuild', methods=['POST'])
def rebuild_baseline():
    """K-means行为基线 + 孤立森林模型"""
    try:
        # 1.训练 K-means 岗位基线
        result = analyzer.train_user_baseline_kmeans()

        # 2.训练孤立森林异常检测模型
        analyzer.train_isolation_forest()

        return jsonify(result)
    except Exception as e:
        db.session.rollback()
        return jsonify({"code": 500, "msg": f"基线重建失败：{str(e)}"})


@baseline_bp.route('/status', methods=['GET'])
def get_baseline_status():
    """查询基线状态"""
    config = AlgorithmConfig.query.first()
    return jsonify({
        "code": 200,
        "baseline_exists": bool(config.baseline_data),
        "wma_window": config.wma_window,
        "k_clusters": config.k_clusters
    })


@baseline_bp.route('/clusters/visualization', methods=['GET'])
def get_clusters_visualization():
    """
    【新增】获取K-means聚类可视化数据
    返回每个聚类的特征和成员信息，用于前端展示
    """
    try:
        config = AlgorithmConfig.query.first()
        if not config or not config.baseline_data:
            return jsonify({
                "code": 404,
                "message": "尚未训练K-means模型，请先点击刷新基线"
            })
        
        # 解析基线数据
        baseline_data = json.loads(config.baseline_data)
        
        # 适配实际数据结构：cluster_centers + user_clusters
        cluster_centers = baseline_data.get('cluster_centers', [])
        user_clusters = baseline_data.get('user_clusters', {})
        
        if not cluster_centers:
            return jsonify({
                "code": 404,
                "message": "聚类数据为空，请重新训练"
            })
        
        # 按聚类分组用户
        from collections import defaultdict
        cluster_members = defaultdict(list)
        all_user_ids = set()  # 【性能优化】收集所有 user_id
        
        for user_id_str, cluster_id in user_clusters.items():
            user_id = int(user_id_str)
            cluster_members[cluster_id].append(user_id)
            all_user_ids.add(user_id)
        
        # 【性能优化】批量查询所有用户，避免 N+1 查询
        users_map = {}
        if all_user_ids:
            users = User.query.filter(User.id.in_(list(all_user_ids))).all()
            users_map = {u.id: u for u in users}
        
        # 构建可视化数据
        visualization_data = []
        for cluster_id, center in enumerate(cluster_centers):
            members = cluster_members.get(cluster_id, [])
            
            # 【性能优化】从字典中获取用户信息，不再查数据库
            member_details = []
            for user_id in members:
                user = users_map.get(user_id)
                if user:
                    member_details.append({
                        'user_id': user.id,
                        'name': user.name,
                        'department': user.department,
                        'position': user.position,
                        'trust_score': user.trust_score
                    })
            
            # 转换center为字典格式（特征名：值）
            feature_names = ['file_ops', 'usb_access', 'login_hours', 'email_sent', 'browser_visits']
            center_features = {}
            for i, value in enumerate(center):
                if i < len(feature_names):
                    center_features[feature_names[i]] = float(value)
            
            # 分析该群组中的主要部门
            dept_counter = defaultdict(int)
            for member in member_details:
                if member.get('department'):
                    dept_counter[member['department']] += 1
            
            # 获取最多的部门作为群组名称
            main_dept = max(dept_counter.items(), key=lambda x: x[1])[0] if dept_counter else '未知部门'
            
            visualization_data.append({
                'cluster_id': cluster_id,
                'cluster_name': f'岗位群组 {cluster_id + 1}',
                'member_count': len(members),
                'center_features': center_features,
                'members': member_details[:10],  # 只返回前10个成员，避免数据过大
                'total_members': len(members),
                'main_department': main_dept  # 保留主要部门字段供参考
            })
        
        return jsonify({
            "code": 200,
            "data": {
                "clusters": visualization_data,
                "total_clusters": len(cluster_centers),
                "k_value": config.k_clusters
            }
        })
    
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取聚类数据失败: {str(e)}"
        })


@baseline_bp.route('/user/<int:user_id>/wma', methods=['GET'])
def get_user_wma_baseline(user_id):
    """
    【优化】获取指定用户的信任分日变化趋势
    基于该员工所有行为日志中的最近14天，计算每日信任分平均值
    """
    try:
        # 获取用户信息
        user = User.query.get(user_id)
        if not user:
            return jsonify({"code": 404, "message": "用户不存在"})
        
        # 获取用户所有行为日志，按时间降序排序
        from core.db import BehaviorLog
        all_logs = BehaviorLog.query.filter_by(user_id=user_id).order_by(BehaviorLog.timestamp.desc()).all()
        
        if not all_logs:
            return jsonify({
                "code": 200,
                "data": {
                    "user_name": user.name,
                    "department": user.department,
                    "current_score": user.trust_score,
                    "daily_trust_trend": [],
                    "message": "暂无行为数据"
                }
            })
        
        # 【核心逻辑】基于该用户最后一条日志时间，向前推14天
        latest_timestamp = all_logs[0].timestamp  # 最新一条日志时间
        from datetime import timedelta
        start_date = latest_timestamp - timedelta(days=13)  # 向前推13天（共14天）
        
        # 筛选最近14天的日志
        recent_logs = [log for log in all_logs if log.timestamp >= start_date]
        
        if not recent_logs:
            return jsonify({
                "code": 200,
                "data": {
                    "user_name": user.name,
                    "department": user.department,
                    "current_score": user.trust_score,
                    "daily_trust_trend": [],
                    "message": "最近14天无行为数据"
                }
            })
        
        # 按日期分组，计算每日信任分表现
        # 【核心修改】由于历史日志中的 trust_score 字段多为初始值 (100)，无法反映波动
        # 这里改为基于 anomaly_score 计算当日的“行为表现信任分”，更直观反映当天的安全状态
        from collections import defaultdict
        daily_data = defaultdict(lambda: {'anomaly_scores': [], 'count': 0, 'high_risk_count': 0})
        
        for log in recent_logs:
            # 提取日期（YYYY-MM-DD）
            date_str = log.timestamp.strftime('%Y-%m-%d')
            daily_data[date_str]['anomaly_scores'].append(log.anomaly_score)
            daily_data[date_str]['count'] += 1
            
            # 统计高风险行为（异常分 >= 0.8）
            if log.anomaly_score >= 0.8:
                daily_data[date_str]['high_risk_count'] += 1
        
        # 构建按日期升序排列的趋势数据
        trend_data = []
        for date_str in sorted(daily_data.keys()):  # 按日期升序排序
            scores = daily_data[date_str]['anomaly_scores']
            avg_anomaly = sum(scores) / len(scores)
            
            # 将平均异常分转换为信任表现分 (0.0异常分 -> 100分, 1.0异常分 -> 0分)
            # 加入平滑系数，避免微小波动导致曲线过于敏感
            daily_trust_score = max(0, min(100, 100 - (avg_anomaly * 100)))
            
            # 计算最高/最低表现分
            min_trust = max(0, min(100, 100 - (max(scores) * 100)))
            max_trust = max(0, min(100, 100 - (min(scores) * 100)))
            
            trend_data.append({
                'date': date_str,
                'avg_trust_score': round(daily_trust_score, 2),
                'behavior_count': daily_data[date_str]['count'],
                'high_risk_count': daily_data[date_str]['high_risk_count'],
                'min_score': round(min_trust, 2),
                'max_score': round(max_trust, 2)
            })
        
        return jsonify({
            "code": 200,
            "data": {
                "user_name": user.name,
                "department": user.department,
                "current_score": user.trust_score,
                "daily_trust_trend": trend_data,
                "total_days": len(trend_data),
                "date_range": {
                    "start": trend_data[0]['date'] if trend_data else None,
                    "end": trend_data[-1]['date'] if trend_data else None
                }
            }
        })
    
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取信任分趋势失败: {str(e)}"
        })


@baseline_bp.route('/users', methods=['GET'])
def get_all_users():
    """
    【新增】获取所有用户列表（用于行为基线页面）
    """
    try:
        users = User.query.all()
        user_list = [{
            'id': user.id,
            'name': user.name,
            'department': user.department,
            'position': user.position,
            'trust_score': user.trust_score,
            'status': user.status
        } for user in users]
        
        return jsonify({
            "code": 200,
            "data": user_list,
            "total": len(user_list)
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"获取用户列表失败: {str(e)}"
        })