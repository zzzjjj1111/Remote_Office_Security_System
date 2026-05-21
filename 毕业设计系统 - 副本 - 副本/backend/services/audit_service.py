"""
审计日志服务 - 记录全链路操作日志
支持身份认证、权限变更、设备状态、OA访问等日志记录
"""
import json
from datetime import datetime
from flask import request, g
from core.db import db, AuditLog, User, Device, BehaviorLog, OaAccessLog


class AuditLogger:
    """审计日志记录器"""
    
    @staticmethod
    def log_auth(user_id, action, status='success', description='', error_message=''):
        """
        记录身份认证日志
        
        Args:
            user_id: 用户ID
            action: 操作类型（login, logout, login_failed, password_change等）
            status: 状态（success/failure/warning）
            description: 描述信息
            error_message: 错误信息
        """
        try:
            audit_log = AuditLog(
                log_type='auth',
                user_id=user_id,
                action=action,
                module='AUTH',  # 【修改】统一为大写
                description=description,
                ip_address=request.remote_addr if request else None,
                user_agent=request.headers.get('User-Agent') if request else None,
                request_method=request.method if request else None,
                request_path=request.path if request else None,
                status=status,
                error_message=error_message if status == 'failure' else None,
                created_at=datetime.now()
            )
            db.session.add(audit_log)
            db.session.commit()
            try:
                print(f"[Audit] Auth Log: {action} - {status}")
            except OSError:
                # Windows控制台编码问题时的备选方案
                print(f"[Audit] Auth Log: {action} - {status}")
        except Exception as e:
            db.session.rollback()
            print(f"[Audit] Failed to log auth: {e}")
    
    @staticmethod
    def log_permission_change(user_id, old_value, new_value, description=''):
        """
        记录权限变更日志
        
        Args:
            user_id: 用户ID
            old_value: 旧值（字典或JSON字符串）
            new_value: 新值（字典或JSON字符串）
            description: 描述信息
        """
        try:
            # 转换为JSON字符串
            if isinstance(old_value, dict):
                old_value_str = json.dumps(old_value, ensure_ascii=False)
            else:
                old_value_str = str(old_value)
            
            if isinstance(new_value, dict):
                new_value_str = json.dumps(new_value, ensure_ascii=False)
            else:
                new_value_str = str(new_value)
            
            audit_log = AuditLog(
                log_type='permission',
                user_id=user_id,
                action='permission_change',
                module='SYSTEM',  # 【修改】统一为大写
                description=description or f'权限变更: {old_value} → {new_value}',
                ip_address=request.remote_addr if request else None,
                request_method=request.method if request else None,
                request_path=request.path if request else None,
                status='success',
                old_value=old_value_str,
                new_value=new_value_str,
                created_at=datetime.now()
            )
            db.session.add(audit_log)
            db.session.commit()
            try:
                print(f"[Audit] Permission Change: user_id={user_id}")
            except OSError:
                # Windows控制台编码问题时的备选方案
                print(f"[Audit] Permission Change: user_id={user_id}")
        except Exception as e:
            db.session.rollback()
            print(f"[Audit] Failed to log permission change: {e}")
    
    @staticmethod
    def log_trust_score_update(user_id, old_score, new_score, reason=''):
        """
        记录信任分更新日志
        
        Args:
            user_id: 用户ID
            old_score: 旧信任分
            new_score: 新信任分
            reason: 更新原因
        """
        try:
            description = f'信任分更新: {old_score:.2f} → {new_score:.2f}'
            if reason:
                description += f' (原因: {reason})'
            
            audit_log = AuditLog(
                log_type='permission',
                user_id=user_id,
                action='trust_score_update',
                module='SYSTEM',  # 【修改】统一为大写
                description=description,
                status='success',
                old_value=json.dumps({'trust_score': round(old_score, 2)}),
                new_value=json.dumps({'trust_score': round(new_score, 2)}),
                created_at=datetime.now()
            )
            db.session.add(audit_log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[Audit] Failed to log trust score update: {e}")
    
    @staticmethod
    def log_device_status(device_id, user_id, action, status='success', description=''):
        """
        记录设备状态日志
        
        Args:
            device_id: 设备ID
            user_id: 用户ID
            action: 操作类型（health_check, compliance_change, register等）
            status: 状态
            description: 描述信息
        """
        try:
            audit_log = AuditLog(
                log_type='device',
                user_id=user_id,
                device_id=device_id,
                action=action,
                module='HEALTH',  # 【修改】统一为大写
                description=description,
                status=status,
                created_at=datetime.now()
            )
            db.session.add(audit_log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[Audit] Failed to log device status: {e}")
    
    @staticmethod
    def log_oa_access(user_id, action, description='', status='success'):
        """
        记录OA访问日志
        
        Args:
            user_id: 用户ID
            action: 操作类型（view_homepage, submit_approval, view_expense等）
            description: 描述信息
            status: 状态
        """
        try:
            audit_log = AuditLog(
                log_type='oa_access',
                user_id=user_id,
                action=action,
                module='OA_ACCESS',  # 【修改】统一为大写
                description=description,
                ip_address=request.remote_addr if request else None,
                request_method=request.method if request else None,
                request_path=request.path if request else None,
                status=status,
                created_at=datetime.now()
            )
            db.session.add(audit_log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[Audit] Failed to log OA access: {e}")
    
    @staticmethod
    def log_behavior(user_id, device_id, behavior_type, description='', anomaly_score=0.0):
        """
        记录行为日志（简化版，详细行为由BehaviorLog记录）
        
        Args:
            user_id: 用户ID
            device_id: 设备ID
            behavior_type: 行为类型
            description: 描述信息
            anomaly_score: 异常分数
        """
        try:
            status = 'warning' if anomaly_score > 0.7 else 'success'
            audit_log = AuditLog(
                log_type='behavior',
                user_id=user_id,
                device_id=device_id,
                action=behavior_type,
                module='BEHAVIOR',  # 【修改】统一为大写
                description=description,
                status=status,
                created_at=datetime.now()
            )
            db.session.add(audit_log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[Audit] Failed to log behavior: {e}")
    
    @staticmethod
    def log_system(action, description='', status='success', error_message=''):
        """
        记录系统级日志
        
        Args:
            action: 操作类型
            description: 描述信息
            status: 状态
            error_message: 错误信息
        """
        try:
            audit_log = AuditLog(
                log_type='system',
                action=action,
                module='SYSTEM',  # 【修改】统一为大写
                description=description,
                status=status,
                error_message=error_message if status == 'failure' else None,
                created_at=datetime.now()
            )
            db.session.add(audit_log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[Audit] Failed to log system event: {e}")
    
    @staticmethod
    def get_audit_logs(log_type=None, user_id=None, start_date=None, end_date=None, 
                       page=1, per_page=50, keyword=None):
        """
        聚合查询全链路审计日志（合并 AuditLog, OaAccessLog, BehaviorLog）
        """
        try:
            # 【性能优化】先收集所有需要查询的 user_id，然后批量查询
            all_logs = []
            all_user_ids = set()

            # 1. 获取 AuditLog (标准审计日志)
            audit_query = AuditLog.query
            if log_type in ['auth', 'permission', 'system', 'device']:
                 audit_query = audit_query.filter(AuditLog.log_type == log_type)
            elif log_type == 'oa_access':
                 audit_query = audit_query.filter(AuditLog.log_type == 'oa_access')
            elif log_type == 'behavior':
                 audit_query = audit_query.filter(AuditLog.log_type == 'behavior')
            
            if user_id: audit_query = audit_query.filter(AuditLog.user_id == user_id)
            if start_date: audit_query = audit_query.filter(AuditLog.created_at >= start_date)
            if end_date: audit_query = audit_query.filter(AuditLog.created_at <= end_date)

            audit_items = audit_query.all()
            for log in audit_items:
                if log.user_id:
                    all_user_ids.add(log.user_id)
                all_logs.append({
                    'id': log.id,  # 【新增】添加日志ID
                    'time': log.created_at,
                    'user_id': log.user_id,
                    'action': log.action,
                    'target': log.module or 'System',
                    'detail': log.description,
                    'ip': log.ip_address or '127.0.0.1',
                    'source': 'audit',
                    'log_type': log.log_type
                })

            # 2. 获取 OaAccessLog (OA 系统流水)
            if log_type is None or log_type == 'oa_access' or log_type == 'all':
                oa_query = OaAccessLog.query
                if user_id: oa_query = oa_query.filter(OaAccessLog.user_id == user_id)
                if start_date: oa_query = oa_query.filter(OaAccessLog.created_at >= start_date)
                if end_date: oa_query = oa_query.filter(OaAccessLog.created_at <= end_date)

                oa_items = oa_query.all()
                for log in oa_items:
                    current_type = 'oa_access'
                    if 'login' in log.operate_type:
                        current_type = 'auth'
                    
                    if log_type is None or log_type == current_type or log_type == 'all':
                        all_logs.append({
                            'id': log.id,  # 【新增】添加日志ID
                            'time': log.created_at,
                            'user_id': log.user_id,
                            'user_name': log.username,  # OA表已经有username，直接用
                            'action': log.operate_type,
                            'target': 'OA_SYSTEM',
                            'detail': log.operate_desc,
                            'ip': log.client_ip or '10.0.0.1',
                            'source': 'oa_access',
                            'log_type': current_type
                        })

            # 3. 获取 BehaviorLog (终端行为感知)
            if log_type is None or log_type == 'behavior' or log_type == 'device' or log_type == 'all':
                beh_query = BehaviorLog.query
                if user_id: beh_query = beh_query.filter(BehaviorLog.user_id == user_id)
                if start_date: beh_query = beh_query.filter(BehaviorLog.timestamp >= start_date)
                if end_date: beh_query = beh_query.filter(BehaviorLog.timestamp <= end_date)

                beh_items = beh_query.all()
                for log in beh_items:
                    if log.user_id:
                        all_user_ids.add(log.user_id)
                    if log.behavior_type in ['usb_device']:
                        current_type = 'device'
                    else:
                        current_type = 'behavior'
                    
                    if log_type is None or log_type == current_type or log_type == 'all':
                        # 【新增】解析专用字段
                        file_info = {}
                        email_info = {}
                        browser_info = {}
                        try:
                            if log.file_op_info:
                                file_info = json.loads(log.file_op_info)
                            if log.email_op_info:
                                email_info = json.loads(log.email_op_info)
                            if log.browser_op_info:
                                browser_info = json.loads(log.browser_op_info)
                        except Exception as e:
                            pass

                        all_logs.append({
                            'id': log.id,  # 【新增】添加日志ID
                            'time': log.timestamp,
                            'user_id': log.user_id,
                            'action': log.behavior_type,
                            'target': 'TERMINAL_BEHAVIOR',
                            'detail': log.action_detail,
                            'ip': log.ip_address or 'Unknown',
                            'source': 'behavior',
                            'log_type': current_type,
                            # 【新增】专用字段数据
                            'file_operation': file_info,
                            'email_operation': email_info,
                            'browser_operation': browser_info,
                            'network_type': log.network_type,
                            'location_hint': log.location_hint,
                            'is_screen_sharing': log.is_screen_sharing,
                            'screen_share_app': log.screen_share_app
                        })

            # 【性能优化】批量查询所有用户，避免 N+1 查询
            users_map = {}
            if all_user_ids:
                users = User.query.filter(User.id.in_(list(all_user_ids))).all()
                users_map = {u.id: u.name for u in users}

            # 填充用户名
            for log in all_logs:
                if log.get('user_name') is None and log.get('user_id'):
                    log['user'] = users_map.get(log['user_id'], 'Unknown')
                elif log.get('user_name'):
                    log['user'] = log['user_name']
                else:
                    log['user'] = 'Unknown'

            # 4. 【新增】关键字搜索过滤
            if keyword:
                kw = keyword.lower()
                all_logs = [
                    log for log in all_logs 
                    if kw in log['user'].lower() or 
                       kw in log['action'].lower() or 
                       kw in log['detail'].lower() or 
                       kw in log['ip'].lower()
                ]

            # 5. 统一按时间倒序排序
            all_logs.sort(key=lambda x: x['time'], reverse=True)

            # 6. 内存分页
            total_count = len(all_logs)
            start_index = (page - 1) * per_page
            end_index = start_index + per_page
            paginated_logs = all_logs[start_index:end_index]

            # 7. 格式化时间输出
            formatted_logs = []
            for log in paginated_logs:
                formatted_logs.append({
                    'id': log.get('id'),
                    'created_at': log['time'].strftime('%Y-%m-%d %H:%M:%S') if log['time'] else '',
                    'user_name': log['user'],
                    'action': log['action'],
                    'module': log['target'],
                    'description': log['detail'],
                    'ip_address': log['ip'],
                    'status': 'warning' if 'fail' in str(log['action']).lower() or 'deny' in str(log['action']).lower() else 'success',
                    'log_type': log['log_type']
                })

            return {
                'code': 200,
                'data': {
                    'logs': formatted_logs,
                    'total': total_count,
                    'page': page,
                    'per_page': per_page,
                    'pages': (total_count + per_page - 1) // per_page
                }
            }
        except Exception as e:
            return {
                'code': 500,
                'message': f'查询失败: {str(e)}'
            }
    
    @staticmethod
    def get_audit_statistics(days=7):
        """
        获取审计统计数据
        
        Args:
            days: 统计天数
            
        Returns:
            dict: 统计数据
        """
        try:
            from datetime import timedelta
            start_date = datetime.now() - timedelta(days=days)
            
            # 各类型日志数量
            type_stats = {}
            for log_type in ['auth', 'permission', 'behavior', 'device', 'oa_access', 'system']:
                count = AuditLog.query.filter(
                    AuditLog.log_type == log_type,
                    AuditLog.created_at >= start_date
                ).count()
                type_stats[log_type] = count
            
            # 成功/失败统计
            success_count = AuditLog.query.filter(
                AuditLog.status == 'success',
                AuditLog.created_at >= start_date
            ).count()
            
            failure_count = AuditLog.query.filter(
                AuditLog.status == 'failure',
                AuditLog.created_at >= start_date
            ).count()
            
            warning_count = AuditLog.query.filter(
                AuditLog.status == 'warning',
                AuditLog.created_at >= start_date
            ).count()
            
            # 总日志数
            total_count = AuditLog.query.filter(
                AuditLog.created_at >= start_date
            ).count()
            
            return {
                'code': 200,
                'data': {
                    'total_logs': total_count,
                    'success_count': success_count,
                    'failure_count': failure_count,
                    'warning_count': warning_count,
                    'type_distribution': type_stats,
                    'period_days': days
                }
            }
        except Exception as e:
            return {
                'code': 500,
                'message': f'统计失败: {str(e)}'
            }


# 全局单例
audit_logger = AuditLogger()
