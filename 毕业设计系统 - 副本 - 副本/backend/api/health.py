"""
终端健康基线检查API
提供设备健康状态检查、合规查询等功能
"""
from flask import Blueprint, request, jsonify
from services.health_check_service import TerminalHealthChecker
from core.db import db, Device, User
from datetime import datetime

health_bp = Blueprint('health', __name__)


@health_bp.route('/check', methods=['POST'])
def check_device_health():
    """
    设备健康检查接口
    接收设备上报的健康数据，进行合规判定
    
    Request Body:
    {
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "patch_status": "已更新",
        "antivirus_status": "Windows Defender 正常",
        "user_id": 1  # 可选
    }
    
    Response:
    {
        "code": 200,
        "compliance_status": "compliant",
        "risk_score": 0,
        "issues": [],
        "action": "pass"  # pass/warn/block
    }
    """
    try:
        data = request.get_json()
        
        mac_address = data.get('mac_address')
        patch_status = data.get('patch_status', '未知')
        antivirus_status = data.get('antivirus_status', '未知')
        user_id = data.get('user_id')
        
        if not mac_address:
            return jsonify({
                'code': 400,
                'msg': '缺少mac_address参数'
            }), 400
        
        # 执行健康检查
        result = TerminalHealthChecker.check_device_health(
            mac_address=mac_address,
            patch_status=patch_status,
            antivirus_status=antivirus_status,
            user_id=user_id
        )
        
        if result['code'] != 200:
            return jsonify(result), 500
        
        # 根据合规状态返回动作建议
        action = 'pass'
        if result['compliance_status'] == 'non_compliant':
            action = 'block'
        elif result['compliance_status'] == 'warning':
            action = 'warn'
        
        return jsonify({
            'code': 200,
            'compliance_status': result['compliance_status'],
            'risk_score': result['risk_score'],
            'issues': result['issues'],
            'action': action,
            'device_id': result['device_id']
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'code': 500,
            'msg': f'健康检查失败：{str(e)}'
        }), 500


@health_bp.route('/stats', methods=['GET'])
def get_health_stats():
    """
    获取整体健康合规统计
    
    Response:
    {
        "code": 200,
        "data": {
            "total_devices": 100,
            "compliant_devices": 85,
            "warning_devices": 10,
            "non_compliant_devices": 5,
            "compliance_rate": 85.0,
            "non_compliant_list": [...]
        }
    }
    """
    try:
        result = TerminalHealthChecker.get_compliance_stats()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取统计失败：{str(e)}'
        }), 500


@health_bp.route('/devices/<int:device_id>', methods=['GET'])
def get_device_health(device_id):
    """
    获取单个设备的健康状态
    
    Response:
    {
        "code": 200,
        "data": {
            "device_id": 1,
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "os_info": "Windows 10",
            "patch_status": "已更新",
            "antivirus_status": "Windows Defender 正常",
            "compliance_status": "compliant",
            "last_health_check": "2024-01-01 12:00:00",
            "user_name": "张三"
        }
    }
    """
    try:
        device = Device.query.get(device_id)
        if not device:
            return jsonify({
                'code': 404,
                'msg': '设备不存在'
            }), 404
        
        user = User.query.get(device.user_id) if device.user_id else None
        
        return jsonify({
            'code': 200,
            'data': {
                'device_id': device.id,
                'mac_address': device.mac_address,
                'os_info': device.os_info,
                'patch_status': device.patch_status or '未知',
                'antivirus_status': device.antivirus_status or '未知',
                'compliance_status': device.compliance_status,
                'last_health_check': device.last_health_check.strftime('%Y-%m-%d %H:%M:%S') if device.last_health_check else '从未检查',
                'user_name': user.name if user else '未知',
                'user_id': user.id if user else None
            }
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取设备信息失败：{str(e)}'
        }), 500


@health_bp.route('/devices', methods=['GET'])
def list_devices_health():
    """
    获取所有设备的健康状态列表（支持分页和过滤）
    
    Query Parameters:
    - page: 页码（默认1）
    - page_size: 每页数量（默认10）
    - compliance_status: 合规状态过滤（compliant/warning/non_compliant）
    - keyword: 搜索关键词（MAC地址或用户名）
    
    Response:
    {
        "code": 200,
        "data": {
            "total": 100,
            "page": 1,
            "page_size": 10,
            "devices": [...]
        }
    }
    """
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        compliance_status = request.args.get('compliance_status')
        keyword = request.args.get('keyword')
        
        # 构建查询
        query = Device.query
        
        if compliance_status:
            query = query.filter_by(compliance_status=compliance_status)
        
        if keyword:
            # 关联用户表进行搜索
            query = query.join(User, Device.user_id == User.id).filter(
                db.or_(
                    Device.mac_address.contains(keyword),
                    User.name.contains(keyword),
                    db.cast(Device.user_id, db.String).contains(keyword)  # 【新增】支持搜索user_id（转为字符串）
                )
            )
        
        # 分页
        pagination = query.paginate(page=page, per_page=page_size, error_out=False)
        
        devices_list = []
        for device in pagination.items:
            user = User.query.get(device.user_id) if device.user_id else None
            devices_list.append({
                'device_id': device.id,
                'mac_address': device.mac_address,
                'os_info': device.os_info,
                'patch_status': device.patch_status or '未知',
                'antivirus_status': device.antivirus_status or '未知',
                'compliance_status': device.compliance_status,
                'last_health_check': device.last_health_check.strftime('%Y-%m-%d %H:%M:%S') if device.last_health_check else '从未检查',
                'user_name': user.name if user else '未知',
                'user_id': user.id if user else None
            })
        
        return jsonify({
            'code': 200,
            'data': {
                'total': pagination.total,
                'page': pagination.page,
                'page_size': pagination.per_page,
                'devices': devices_list
            }
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取设备列表失败：{str(e)}'
        }), 500


@health_bp.route('/compliance-history', methods=['GET'])
def get_compliance_history():
    """
    获取合规趋势历史（最近7天）
    从 behavior_logs 表中按天统计合规率
    
    Response:
    {
        "code": 200,
        "data": {
            "dates": ["5/1", "5/2", ...],
            "compliance_rates": [85.5, 86.2, ...],
            "total_devices": [100, 102, ...],
            "compliant_count": [85, 87, ...]
        }
    }
    """
    try:
        from datetime import timedelta
        from sqlalchemy import text
        
        # 获取当前时间作为基准
        now = datetime.now()
        
        # 查询最近7天的合规数据
        # 逻辑：统计每天的总设备数（有行为日志的设备）和合规设备数
        sql = """
            SELECT 
                DATE(timestamp) as log_date,
                COUNT(DISTINCT device_id) as total_devices,
                COUNT(DISTINCT CASE WHEN trust_score >= 60 THEN device_id END) as compliant_devices
            FROM behavior_logs
            WHERE timestamp >= :start_date
              AND timestamp < :end_date
              AND device_id IS NOT NULL
            GROUP BY DATE(timestamp)
            ORDER BY log_date ASC
        """
        
        start_date = now - timedelta(days=7)
        end_date = now
        
        with db.engine.connect() as conn:
            result = conn.execute(text(sql), {
                'start_date': start_date,
                'end_date': end_date
            })
            
            # 构建日期映射
            date_data = {}
            for row in result:
                log_date = row[0]
                total = row[1]
                compliant = row[2]
                rate = (compliant / total * 100) if total > 0 else 0
                date_data[log_date] = {
                    'total': total,
                    'compliant': compliant,
                    'rate': round(rate, 2)
                }
        
        # 生成完整的7天日期列表（即使某天没有数据也显示）
        dates = []
        compliance_rates = []
        total_devices_list = []
        compliant_count_list = []
        
        for i in range(6, -1, -1):
            target_date = (now - timedelta(days=i)).date()
            dates.append(f"{target_date.month}/{target_date.day}")
            
            if target_date in date_data:
                compliance_rates.append(date_data[target_date]['rate'])
                total_devices_list.append(date_data[target_date]['total'])
                compliant_count_list.append(date_data[target_date]['compliant'])
            else:
                # 无数据时填充0
                compliance_rates.append(0)
                total_devices_list.append(0)
                compliant_count_list.append(0)
        
        return jsonify({
            'code': 200,
            'data': {
                'dates': dates,
                'compliance_rates': compliance_rates,
                'total_devices': total_devices_list,
                'compliant_count': compliant_count_list
            }
        })
        
    except Exception as e:
        print(f"[Error] 获取合规历史失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'code': 500,
            'msg': f'获取合规历史失败：{str(e)}'
        }), 500
