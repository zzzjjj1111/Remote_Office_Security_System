from flask import Flask, jsonify, request
from flask_cors import CORS

from core.db import init_db
from api.auth import auth_bp
from api.behavior import behavior_bp
from api.baseline import baseline_bp
from api.dashboard import dashboard_bp
from api.health import health_bp  # 【新增】终端健康检查API
from api.alerts import alerts_bp  # 【新增】告警管理API
from api.agent_status import agent_status_bp  # 【新增】Agent状态检测API
from api.oa_integration import oa_bp  # 【新增】OA联动API
from api.oa_interaction import oa_interaction_bp  # 【新增】OA功能交互API
from api.audit import audit_bp  # 【新增】审计日志API
from core.config import Config
from core.config_bp import config_bp
import threading
import time

app = Flask(__name__)
app.config.from_object(Config)
app.register_blueprint(config_bp)

# 【修复】使用flask-cors库处理CORS，确保所有响应（包括错误）都有CORS头
CORS(app, 
     resources={r"/api/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"]}},
     supports_credentials=True,
     expose_headers=["Content-Type", "Authorization"])

# 初始化数据库
init_db(app)

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(behavior_bp, url_prefix='/api/behavior')
app.register_blueprint(baseline_bp, url_prefix='/api/baseline')
app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
app.register_blueprint(health_bp, url_prefix='/api/health')  # 【新增】注册健康检查API
app.register_blueprint(alerts_bp)  # 【新增】注册告警管理API
app.register_blueprint(agent_status_bp)  # 【新增】注册Agent状态检测API
app.register_blueprint(oa_bp, url_prefix='/api/oa')  # 【新增】注册OA联动API
app.register_blueprint(oa_interaction_bp, url_prefix='/api')  # 【新增】注册OA功能交互API
app.register_blueprint(audit_bp)  # 【新增】注册审计日志API

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "Zero Trust Terminal Protection System"})

# ===================== 【新增】全局错误处理 =====================
@app.errorhandler(404)
def not_found(error):
    """处理404错误，返回JSON格式"""
    return jsonify({
        "status": "error",
        "message": "请求的资源不存在",
        "error_code": 404
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """处理500错误，返回JSON格式"""
    import traceback
    error_traceback = traceback.format_exc()
    print(f"\n❌ 服务器内部错误:\n{error_traceback}\n")
    
    return jsonify({
        "status": "error",
        "message": "服务器内部错误",
        "error_code": 500,
        "detail": str(error) if app.debug else None
    }), 500

@app.errorhandler(Exception)
def handle_exception(error):
    """处理所有未捕获的异常，返回JSON格式"""
    import traceback
    error_traceback = traceback.format_exc()
    try:
        print(f"\n [Unhandled Exception]:\n{error_traceback}\n")
    except OSError:
        print(f"\n [Unhandled Exception] (encoding issue)\n")
    
    return jsonify({
        "status": "error",
        "message": "Server error occurred",
        "error_code": 500,
        "detail": str(error) if app.debug else None
    }), 500

# ===================== 【新增】孤立森林模型自动训练 =====================
def train_isolation_forest_background():
    """
    后台线程：启动时训练孤立森林模型
    """
    with app.app_context():
        try:
            from services.ml_service import BehaviorAnalyzer
            analyzer = BehaviorAnalyzer()
            print("\n" + "="*60)
            print("🤖 开始训练孤立森林模型...")
            print("="*60)
            
            success = analyzer.train_isolation_forest()
            
            if success:
                print("✅ 孤立森林模型训练成功！")
            else:
                print("⚠️ 孤立森林模型训练失败（数据不足），将在首次检测时重试")
            
            print("="*60 + "\n")
        except Exception as e:
            print(f"❌ 孤立森林模型训练异常: {e}")
            import traceback
            traceback.print_exc()

def scheduled_retrain_iforest(interval_hours=24):
    """
    定时任务：每隔指定小时重新训练孤立森林模型
    
    Args:
        interval_hours: 重训间隔（小时），默认24小时
    """
    with app.app_context():
        while True:
            time.sleep(interval_hours * 3600)  # 转换为秒
            try:
                from services.ml_service import BehaviorAnalyzer
                analyzer = BehaviorAnalyzer()
                print(f"\n{'='*60}")
                print(f"⏰ 定时任务：重新训练孤立森林模型（每{interval_hours}小时）")
                print(f"{'='*60}")
                
                success = analyzer.train_isolation_forest()
                
                if success:
                    print("✅ 孤立森林模型重训成功！")
                else:
                    print("⚠️ 孤立森林模型重训失败")
                
                print(f"{'='*60}\n")
            except Exception as e:
                print(f"❌ 孤立森林模型定时重训异常: {e}")

# 启动时训练孤立森林模型
print("\n🚀 系统启动中...")
train_thread = threading.Thread(target=train_isolation_forest_background, daemon=True)
train_thread.start()

# 启动定时重训任务（后台线程）
retrain_thread = threading.Thread(
    target=scheduled_retrain_iforest, 
    args=(24,),  # 每24小时重训一次
    daemon=True
)
retrain_thread.start()
print("✅ 孤立森林模型训练任务已启动（启动时训练 + 每24小时重训）\n")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
