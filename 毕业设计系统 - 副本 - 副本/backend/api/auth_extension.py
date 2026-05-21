@auth_bp.route('/me', methods=['GET'])
def get_me():
    token = request.headers.get('Authorization', '')
    if not token or not token.startswith('Bearer '):
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    # 简单的 token 解析，结构为 "Bearer token_{id}_{work_wechat_id}"
    try:
        real_token = token.split(' ')[1]
        user_id = int(real_token.split('_')[1])
        user = User.query.get(user_id)
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404
            
        return jsonify({
            "status": "success",
            "data": {
                "id": user.id,
                "name": user.name,
                "department": user.department,
                "position": user.position,
                "trust_score": user.trust_score
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
