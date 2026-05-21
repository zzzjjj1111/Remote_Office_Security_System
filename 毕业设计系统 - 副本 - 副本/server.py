from flask import Flask, request, jsonify
import random

app = Flask(__name__)


# 匹配客户端的接口路径和请求方法
@app.route('/api/behavior/upload', methods=['POST'])
def upload_behavior():
    try:
        # 解析客户端发送的JSON数据（兼容嵌套字典如system_health）
        data = request.get_json()
        if not data:
            return jsonify({"error": "未接收JSON数据"}), 400

        # 模拟信任分数计算（客户端核心期望的返回字段）
        trust_score = random.randint(50, 100)

        # 返回客户端需要的new_trust_score字段
        return jsonify({
            "status": "success",
            "new_trust_score": trust_score,
            "message": "数据接收并处理完成"
        }), 200

    except Exception as e:
        # 打印服务器内部错误（调试关键）
        print(f"服务器错误详情：{str(e)}")
        return jsonify({"error": "内部服务器错误", "detail": str(e)}), 500


if __name__ == "__main__":
    # 启动服务器（绑定127.0.0.1:5000，开启调试模式）
    app.run(host='127.0.0.1', port=5000, debug=True)