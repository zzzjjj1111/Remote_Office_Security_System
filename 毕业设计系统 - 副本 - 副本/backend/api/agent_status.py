"""
Agent状态检测API - 用于OA系统检查员工终端Agent是否运行
"""
from flask import Blueprint, request, jsonify
from core.db import db, User, BehaviorLog
from datetime import datetime, timedelta

agent_status_bp = Blueprint('agent_status', __name__)


@agent_status_bp.route('/api/agent/check-status', methods=['GET'])
def check_agent_running():
    """
    检查指定用户的Agent是否正在运行
    
    判断逻辑：查询该用户最近5分钟内是否有行为数据上报
    如果有，说明Agent正在运行；否则认为Agent未启动
    
    【新增】管理员白名单机制：白名单用户无需启动Agent
    
    Returns:
        {
            "code": 200,
            "data": {
                "is_running": true/false,
                "last_activity": "2024-01-15T10:30:00",
                "minutes_ago": 3,
                "is_whitelisted": true/false  # 【新增】是否为白名单用户
            }
        }
    """
    try:
        # 从Token中获取用户ID
        token = request.headers.get('Authorization', '')
        if not token or not token.startswith('Bearer '):
            return jsonify({'code': 401, 'message': '未授权'}), 401
        
        # 简单解析Token获取user_id（实际应该用JWT解码）
        from services.audit_service import audit_logger
        import jwt as jwt_lib
        
        try:
            real_token = token.split(' ')[1]
            payload = jwt_lib.decode(real_token, 'your-secret-key', algorithms=['HS256'])
            user_id = payload['user_id']
        except Exception as e:
            return jsonify({'code': 401, 'message': f'Token解析失败: {str(e)}'}), 401
        
        # ======== 【核心修复】管理员白名单检测 ========
        from core.config import Config
        user = User.query.get(user_id)
        if not user:
            return jsonify({'code': 404, 'message': '用户不存在'}), 404
        
        # 检查是否在白名单中（职位或ID）
        is_whitelisted = (
            user.position in Config.ADMIN_WHITELIST_POSITIONS or
            user.id in Config.ADMIN_WHITELIST_USER_IDS
        )
        
        if is_whitelisted:
            # 白名单用户直接返回 Agent 运行中，跳过实际检测
            try:
                print(f"✅ [Agent白名单] 用户 {user.name}(ID:{user_id}, 职位:{user.position}) 在白名单中，跳过Agent检测")
            except OSError:
                print(f"[Agent Whitelist] User {user.name}(ID:{user_id}) is whitelisted, skip agent check")
            
            return jsonify({
                'code': 200,
                'message': '白名单用户，无需启动Agent',
                'data': {
                    'is_running': True,  # 强制返回运行中
                    'last_activity': None,
                    'minutes_ago': 0,
                    'is_whitelisted': True,  # 标记为白名单
                    'whitelist_reason': f'职位: {user.position}' if user.position in Config.ADMIN_WHITELIST_POSITIONS else '用户ID在白名单'
                }
            })
        # ============================================
        
        # 查询该用户最近5分钟内的行为日志
        five_minutes_ago = datetime.now() - timedelta(minutes=5)
        recent_log = BehaviorLog.query.filter(
            BehaviorLog.user_id == user_id,
            BehaviorLog.timestamp >= five_minutes_ago
        ).order_by(BehaviorLog.timestamp.desc()).first()
        
        if recent_log:
            # Agent正在运行
            minutes_ago = (datetime.now() - recent_log.timestamp).total_seconds() / 60
            return jsonify({
                'code': 200,
                'data': {
                    'is_running': True,
                    'last_activity': recent_log.timestamp.isoformat(),
                    'minutes_ago': round(minutes_ago, 1),
                    'message': 'Agent正常运行中'
                }
            })
        else:
            # Agent未运行
            # 查询最后一次活动时间
            last_log = BehaviorLog.query.filter_by(
                user_id=user_id
            ).order_by(BehaviorLog.timestamp.desc()).first()
            
            last_activity = None
            minutes_ago = None
            if last_log:
                last_activity = last_log.timestamp.isoformat()
                minutes_ago = (datetime.now() - last_log.timestamp).total_seconds() / 60
            
            return jsonify({
                'code': 200,
                'data': {
                    'is_running': False,
                    'last_activity': last_activity,
                    'minutes_ago': round(minutes_ago, 1) if minutes_ago else None,
                    'message': 'Agent未检测到活动，请启动Agent'
                }
            })
    
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@agent_status_bp.route('/api/agent/start-script', methods=['POST'])
def get_start_script():
    """
    生成Agent启动脚本供用户下载
    
    Returns:
        {
            "code": 200,
            "data": {
                "script_url": "/api/agent/download-script",
                "instructions": "1. 下载脚本\n2. 双击运行\n3. 保持窗口开启"
            }
        }
    """
    try:
        token = request.headers.get('Authorization', '')
        if not token or not token.startswith('Bearer '):
            return jsonify({'code': 401, 'message': '未授权'}), 401
        
        import jwt as jwt_lib
        try:
            real_token = token.split(' ')[1]
            payload = jwt_lib.decode(real_token, 'your-secret-key', algorithms=['HS256'])
            user_id = payload['user_id']
        except Exception as e:
            return jsonify({'code': 401, 'message': 'Token解析失败'}), 401
        
        # 返回脚本下载链接和说明
        return jsonify({
            'code': 200,
            'data': {
                'script_url': f'/api/agent/download-script/{user_id}',
                'instructions': (
                    '📋 启动步骤：\n\n'
                    '1️⃣ 点击下方"下载启动脚本"按钮\n'
                    '2️⃣ 双击运行下载的 .bat 文件（Windows）或 .sh 文件（Mac/Linux）\n'
                    '3️⃣ 保持命令行窗口开启（不要关闭）\n'
                    '4️⃣ 刷新本页面，系统将自动检测Agent状态\n\n'
                    '⚠️ 注意：关闭窗口将停止Agent运行'
                ),
                'user_id': user_id
            }
        })
    
    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500


@agent_status_bp.route('/api/agent/download-script/<int:user_id>', methods=['GET'])
def download_start_script(user_id):
    """
    下载Agent启动脚本
    
    根据操作系统生成对应的启动脚本
    """
    try:
        import platform
        import os
        from flask import send_file
        
        system = platform.system()
        
        # 获取项目根目录的绝对路径
        # backend/api/agent_status.py -> backend -> 项目根目录
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        agent_dir = os.path.join(project_root, 'frontend_agent')
        collector_path = os.path.join(agent_dir, 'collector.py')
        
        # 验证collector.py是否存在
        if not os.path.exists(collector_path):
            return jsonify({
                'code': 500,
                'message': f'找不到collector.py文件，路径: {collector_path}'
            }), 500
        
        if system == 'Windows':
            # 生成Windows批处理脚本（使用绝对路径）
            script_content = f'''@echo off
chcp 65001 >nul
echo ========================================
echo   企业安全客户端 Agent 启动器
echo ========================================
echo.
echo 正在启动监控服务...
echo 用户ID: {user_id}
echo 工作目录: "{agent_dir}"
echo.

cd /d "{agent_dir}"
python collector.py --user {user_id} --interval 10

echo.
echo Agent已停止运行
echo 按任意键退出...
pause >nul
'''
            script_path = os.path.join(agent_dir, f'start_agent_{user_id}.bat')
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            return send_file(
                script_path,
                as_attachment=True,
                download_name=f'start_agent_{user_id}.bat',
                mimetype='application/x-bat'
            )
        
        else:  # macOS/Linux
            # 生成Shell脚本（使用绝对路径）
            script_content = f'''#!/bin/bash

echo "========================================"
echo "  企业安全客户端 Agent 启动器"
echo "========================================"
echo ""
echo "正在启动监控服务..."
echo "用户ID: {user_id}"
echo "工作目录: {agent_dir}"
echo ""

cd "{agent_dir}"
python3 collector.py --user {user_id} --interval 10

echo ""
echo "Agent已停止运行"
read -p "按回车键退出..."
'''
            script_path = os.path.join(agent_dir, f'start_agent_{user_id}.sh')
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            os.chmod(script_path, 0o755)
            
            return send_file(
                script_path,
                as_attachment=True,
                download_name=f'start_agent_{user_id}.sh',
                mimetype='application/x-sh'
            )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'code': 500, 'message': f'生成脚本失败: {str(e)}'}), 500
