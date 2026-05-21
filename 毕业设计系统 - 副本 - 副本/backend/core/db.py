from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db(app):
    db.init_app(app)
    # 不依赖 db.create_all() 因为已经有 schema.sql 手动管理
    
# ---- 数据模型定义 ----
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    work_wechat_id = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    department = db.Column(db.String(100))
    position = db.Column(db.String(100))
    status = db.Column(db.Enum('active', 'blocked'), default='active')
    trust_score = db.Column(db.Float, default=100.0)
    wechat_userid = db.Column(db.String(100), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Device(db.Model):
    __tablename__ = 'devices'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    mac_address = db.Column(db.String(50), unique=True, nullable=False)
    os_info = db.Column(db.String(100))  # 操作系统信息
    patch_status = db.Column(db.String(255))  # 补丁状态：已更新/缺失关键补丁/严重落后
    antivirus_status = db.Column(db.String(255))  # 杀毒软件状态
    last_login_time = db.Column(db.DateTime)  # 最后登录时间
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)  # 设备创建时间
    last_health_check = db.Column(db.DateTime)  # 【新增】最后一次健康检查时间
    compliance_status = db.Column(db.Enum('compliant', 'warning', 'non_compliant'), default='compliant')  # 【新增】合规状态

class BehaviorLog(db.Model):
    __tablename__ = 'behavior_logs'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))
    behavior_type = db.Column(db.String(50))
    action_detail = db.Column(db.Text)
    is_sensitive = db.Column(db.Boolean, default=False)
    anomaly_score = db.Column(db.Float, default=0.0)
    timestamp = db.Column(db.DateTime, default=db.func.now(), server_default=db.func.now())
    trust_score = db.Column(db.Integer, default=100)  # 信任分
    ip_address = db.Column(db.String(50))  # IP地址
    network_type = db.Column(db.String(20))  # 网络类型：office/home/mobile/vpn/unknown
    is_vpn = db.Column(db.Boolean, default=False)  # 是否使用VPN
    location_hint = db.Column(db.String(100))  # 位置提示
    is_screen_sharing = db.Column(db.Boolean, default=False)  # 是否正在屏幕共享
    screen_share_app = db.Column(db.String(100))  # 共享应用名称
    screen_share_type = db.Column(db.String(50))  # 共享类型
    file_op_info = db.Column(db.Text)  # 文件操作信息（JSON格式）
    email_op_info = db.Column(db.Text)  # 邮件操作信息（JSON格式）
    browser_op_info = db.Column(db.Text)  # 浏览器操作信息（JSON格式）

class Alert(db.Model):
    __tablename__ = 'alerts'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    log_id = db.Column(db.BigInteger, db.ForeignKey('behavior_logs.id'))
    alert_level = db.Column(db.Enum('low', 'medium', 'high', 'critical'))
    action_taken = db.Column(db.Enum('warn', 'block'))
    description = db.Column(db.Text)
    is_false_positive = db.Column(db.Boolean, default=False)  # 是否误判
    feedback_type = db.Column(db.Enum('false_positive', 'confirmed', 'pending', 'pending_review', 'user_confirmed', 'user_cancelled'), default='pending')  # 反馈类型
    feedback_time = db.Column(db.DateTime)  # 反馈时间
    feedback_reason = db.Column(db.String(500))  # 反馈原因
    feedback_admin_id = db.Column(db.Integer, db.ForeignKey('users.id'))  # 反馈管理员ID
    baseline_corrected = db.Column(db.Boolean, default=False)  # 基线是否已修正
    correction_time = db.Column(db.DateTime)  # 基线修正时间
    created_at = db.Column(db.DateTime, default=db.func.now())  # 【新增】创建时间
    # 【新增】信任分扣分数值（用于误报时精确恢复）
    trust_score_deducted = db.Column(db.Float, default=0.0)  # 记录该告警导致的信任分扣分数值

class AlgorithmConfig(db.Model):
    __tablename__ = "algorithm_config"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 高风险阈值（默认60分，对应页面初始值）
    trust_threshold = db.Column(db.Integer, default=60, nullable=False)
    # 近3天权重系数（默认0.5，对应页面初始值）
    wma_weight = db.Column(db.Float, default=0.5, nullable=False)
    # 最后更新时间（自动更新）
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    # 存储K-means基线
    baseline_data = db.Column(db.Text, nullable=True)
    # WMA窗口大小
    wma_window = db.Column(db.Integer, default=14)
    # K-means聚类数
    k_clusters = db.Column(db.Integer, default=5)
    # 【新增】工作时间配置（用于判断非工作时间操作）
    work_start_time = db.Column(db.String(10), default="09:30")  # 工作开始时间，格式 HH:MM
    work_end_time = db.Column(db.String(10), default="18:30")    # 工作结束时间，格式 HH:MM

# -------------------------- 新增：敏感词库表 --------------------------
class SensitiveWord(db.Model):
    __tablename__ = "sensitive_words"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 敏感词/特征符（唯一，不可重复）
    word = db.Column(db.String(100), unique=True, nullable=False)
    # 风险定级（高风险/绝密/警告等，对应页面标签颜色）
    risk_level = db.Column(db.String(20), default="高风险", nullable=False)
    # 创建人ID（关联users表，默认ADMIN）
    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # 添加时间（自动生成）
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # 关联用户表，方便查询创建人信息
    creator = db.relationship("User", backref=db.backref("sensitive_words", lazy=True))

# -------------------------- 新增：误判样本记录表 --------------------------
class FalsePositiveSample(db.Model):
    __tablename__ = "false_positive_samples"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    alert_id = db.Column(db.Integer, db.ForeignKey("alerts.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"))
    behavior_type = db.Column(db.String(50))
    anomaly_score = db.Column(db.Float)
    feedback_reason = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now)
    used_for_training = db.Column(db.Boolean, default=False)
    training_time = db.Column(db.DateTime)
    
    # 关联关系
    alert = db.relationship("Alert", backref=db.backref("false_positive_samples", lazy=True))
    user = db.relationship("User", backref=db.backref("false_positive_samples", lazy=True))

# -------------------------- 新增：审计日志表 --------------------------
class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    log_type = db.Column(db.Enum('auth', 'permission', 'behavior', 'device', 'oa_access', 'system', 'source_code'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"))
    action = db.Column(db.String(100), nullable=False)
    module = db.Column(db.String(50))
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.Text)
    request_method = db.Column(db.String(10))
    request_path = db.Column(db.String(255))
    status = db.Column(db.Enum('success', 'failure', 'warning'), default='success')
    error_message = db.Column(db.Text)
    old_value = db.Column(db.Text)  # JSON格式
    new_value = db.Column(db.Text)  # JSON格式
    created_at = db.Column(db.DateTime, default=datetime.now)
    user = db.relationship("User", backref=db.backref("audit_logs", lazy=True))
    device = db.relationship("Device", backref=db.backref("audit_logs", lazy=True))


class OaAccessLog(db.Model):
    __tablename__ = 'oa_access_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    # 操作类型：login_check/access_page/function_call/permission_denied
    operate_type = db.Column(db.String(50), nullable=False)
    operate_desc = db.Column(db.String(200), nullable=True)
    # 访问IP
    client_ip = db.Column(db.String(50), nullable=True)
    # 请求结果：success/fail
    result = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联用户表
    user = db.relationship('User', backref=db.backref('oa_logs', lazy=True))