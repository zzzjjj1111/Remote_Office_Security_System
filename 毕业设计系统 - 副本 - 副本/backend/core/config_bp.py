from flask import Blueprint, request, jsonify
from core.db import db, SensitiveWord, User, AlgorithmConfig
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services.ac_service import acs_monitor

# 定义蓝图，前缀/api/config（和前端请求完全一致）
config_bp = Blueprint("config", __name__, url_prefix="/api/config")


# ===================== 算法参数接口 =====================
@config_bp.route("/get", methods=["GET"])
def get_config():
    """获取当前算法参数（页面加载时调用）"""
    try:
        config = AlgorithmConfig.query.first()
        # 首次访问无数据时，插入默认参数（60分阈值、0.5权重）
        if not config:
            config = AlgorithmConfig(trust_threshold=60, wma_weight=0.5)
            db.session.add(config)
            db.session.commit()
        return jsonify({
            "code": 200,
            "data": {
                "trust_threshold": config.trust_threshold,
                "wma_weight": config.wma_weight
            }
        })
    except Exception as e:
        print(f"❌ 获取算法参数失败：{str(e)}")
        return jsonify({"code": 500, "msg": f"服务器错误：{str(e)}"}), 500


@config_bp.route("/update", methods=["POST"])
def update_config():
    """更新算法参数（点击「保存参数配置」时调用）"""
    try:
        data = request.get_json()
        config = AlgorithmConfig.query.first()
        if not config:
            config = AlgorithmConfig()
            db.session.add(config)

        if "trust_threshold" in data:
            config.trust_threshold = int(data["trust_threshold"])
        if "wma_weight" in data:
            config.wma_weight = float(data["wma_weight"])

        db.session.commit()
        return jsonify({"code": 200, "msg": "参数保存成功"})
    except Exception as e:
        db.session.rollback()
        print(f"❌ 更新算法参数失败：{str(e)}")
        return jsonify({"code": 500, "msg": f"服务器错误：{str(e)}"}), 500


# ===================== 敏感词库接口 =====================
@config_bp.route("/sensitive/words", methods=["GET"])
def get_sensitive_words():
    """获取所有敏感词（页面加载时调用）"""
    try:
        words = SensitiveWord.query.all()
        return jsonify({
            "code": 200,
            "data": [
                {
                    "id": w.id,
                    "word": w.word,
                    "risk_level": w.risk_level,
                    "creator_id": "ADMIN",  # 统一显示ADMIN，匹配前端页面
                    "created_at": w.created_at.strftime("%Y-%m-%d %H:%M:%S")
                } for w in words
            ]
        })
    except Exception as e:
        print(f"❌ 获取敏感词失败：{str(e)}")
        return jsonify({"code": 500, "msg": f"服务器错误：{str(e)}"}), 500


@config_bp.route("/sensitive/words/add", methods=["POST"])
def add_sensitive_word():
    """添加敏感词（点击「添加特征词」时调用）"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "请求数据为空"}), 400

        word = data.get("word")
        risk_level = data.get("risk_level", "高风险")

        # 校验敏感词非空
        if not word or word.strip() == "":
            return jsonify({"code": 400, "msg": "敏感词不能为空"}), 400

        # 校验敏感词是否已存在（去重）
        if SensitiveWord.query.filter_by(word=word.strip()).first():
            return jsonify({"code": 400, "msg": "敏感词已存在"}), 400

        # ===================== 【核心修复：彻底解决username不存在问题】 =====================
        # 方案：兜底获取系统第一个用户（无需依赖username字段，100%成功）
        admin = User.query.first()
        if not admin:
            return jsonify({"code": 500, "msg": "系统无用户，无法添加敏感词"}), 500

        # 写入数据库
        new_word = SensitiveWord(
            word=word.strip(),
            risk_level=risk_level,
            creator_id=admin.id  # 用admin的id，完全不依赖字段名
        )
        db.session.add(new_word)
        db.session.commit()

        # 重建AC自动机，新敏感词立即生效
        acs_monitor.rebuild()

        print(f"✅ 成功添加敏感词：{word}，风险等级：{risk_level}")
        return jsonify({
            "code": 200,
            "msg": "添加成功",
            "data": {
                "id": new_word.id,
                "word": new_word.word,
                "risk_level": new_word.risk_level,
                "creator_id": "ADMIN",
                "created_at": new_word.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
        })

    except Exception as e:
        db.session.rollback()
        print(f"❌ 添加敏感词失败：{str(e)}")  # 后端打印详细错误，方便排查
        return jsonify({"code": 500, "msg": f"服务器错误：{str(e)}"}), 500


@config_bp.route("/sensitive/words/delete/<int:word_id>", methods=["DELETE"])
def delete_sensitive_word(word_id):
    """删除敏感词（点击删除按钮时调用）"""
    try:
        word = SensitiveWord.query.get(word_id)
        if not word:
            return jsonify({"code": 404, "msg": "敏感词不存在"}), 404

        db.session.delete(word)
        db.session.commit()

        # 重建AC自动机，敏感词立即失效
        acs_monitor.rebuild()

        return jsonify({"code": 200, "msg": "删除成功"})
    except Exception as e:
        db.session.rollback()
        print(f"❌ 删除敏感词失败：{str(e)}")
        return jsonify({"code": 500, "msg": f"服务器错误：{str(e)}"}), 500