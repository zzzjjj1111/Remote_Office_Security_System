from flask import Blueprint, jsonify, request
from core.db import db
from sqlalchemy import text
from datetime import datetime, timedelta

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/stats', methods=['GET'])
def get_stats():
    """
    获取安全总览统计数据
    
    返回真实数据库中的统计信息:
    - total_devices: 注册终端设备总数
    - high_risk_events: 高危告警数量 (alert_level='high')
    - blocked_events: 被阻断的操作数量 (action_taken='block')
    - compliance_rate: 设备合规率 (补丁已更新且杀毒软件正常)
    """
    try:
        with db.engine.connect() as conn:
            # 1. 当前防护终端数 - 统计所有注册设备
            devices_count = conn.execute(text("SELECT COUNT(*) FROM devices")).scalar()
            
            # 2. 异常行为检测数 - 统计高危级别告警 (high)
            # 【修复】已将 critical 改为 high，符合当前系统的三级告警体系
            high_risk_count = conn.execute(
                text("SELECT COUNT(*) FROM alerts WHERE alert_level='high'")
            ).scalar()
            
            # 3. 敏感操作拦截数 - 统计执行了阻断操作的告警
            blocked_count = conn.execute(
                text("SELECT COUNT(*) FROM alerts WHERE action_taken='block'")
            ).scalar()
            
            # 4. 终端行为合规率 - 设备健康状态统计
            # 合规标准: 补丁已更新 AND 杀毒软件正常
            healthy_devices = conn.execute(
                text("SELECT COUNT(*) FROM devices WHERE patch_status='已更新' AND antivirus_status LIKE '%正常%'")
            ).scalar()
            
            complianceRate = round((healthy_devices / devices_count) * 100) if devices_count > 0 else 0
            
            return jsonify({
                "status": "success",
                "data": {
                    "total_devices": devices_count,
                    "high_risk_events": high_risk_count or 0,
                    "blocked_events": blocked_count or 0,
                    "compliance_rate": f"{complianceRate}%"
                }
            })
    except Exception as e:
        print(f"[Error] 获取Dashboard统计数据失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e),
            "data": {
                "total_devices": 0,
                "high_risk_events": 0,
                "blocked_events": 0,
                "compliance_rate": "0%"
            }
        }), 500

@dashboard_bp.route('/trust-trend', methods=['GET'])
def get_trust_trend():
    """
    获取动态信任基线趋势数据
    从 behavior_logs 表中按小时统计平均 trust_score
    支持查询最近3天的数据（按相对日期）
    """
    try:
        # 获取日期参数（today/yesterday/dayBeforeYesterday）
        day_param = request.args.get('day', 'today')
        
        # 【修复】使用相对日期查询
        # 先找出数据库中有数据的最近一天
        sql_find_latest = """
            SELECT DATE(timestamp) as log_date
            FROM behavior_logs
            GROUP BY DATE(timestamp)
            ORDER BY log_date DESC
            LIMIT 1
        """
        
        with db.engine.connect() as conn:
            latest_result = conn.execute(text(sql_find_latest))
            latest_row = latest_result.fetchone()
            
            if not latest_row:
                # 数据库中没有数据
                return jsonify({
                    "status": "success",
                    "data": {
                        "hours": [f"{h:02d}:00" for h in range(24)],
                        "trust_scores": [0] * 24
                    }
                })
            
            latest_date = latest_row[0]  # 数据库中最晚的日期
            
            # 根据参数计算目标日期
            from datetime import timedelta
            if day_param == 'today':
                target_date = latest_date
            elif day_param == 'yesterday':
                target_date = latest_date - timedelta(days=1)
            elif day_param == 'dayBeforeYesterday':
                target_date = latest_date - timedelta(days=2)
            else:
                target_date = latest_date
            
            # 查询目标日期的按小时平均信任分
            sql = """
                SELECT 
                    HOUR(timestamp) as hour,
                    AVG(trust_score) as avg_trust_score
                FROM behavior_logs
                WHERE DATE(timestamp) = :target_date
                GROUP BY HOUR(timestamp)
                ORDER BY hour
            """
            
            result = conn.execute(text(sql), {'target_date': target_date})
            
            # 初始化24小时数据（默认值为0）
            hourly_data = [0] * 24
            
            # 填充实际数据
            for row in result:
                hour = row[0]
                avg_score = float(row[1]) if row[1] else 0
                hourly_data[hour] = round(avg_score, 2)
            
            return jsonify({
                "status": "success",
                "data": {
                    "hours": [f"{h:02d}:00" for h in range(24)],
                    "trust_scores": hourly_data,
                    "query_date": str(target_date)  # 返回实际查询的日期，方便调试
                }
            })
    except Exception as e:
        print(f"[Error] 获取信任趋势失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
