import requests
import json

# 测试AC自动机是否正常工作
test_data = {
    "is_frontend_mock": True,
    "mock_user_id": 20,  # 使用你的测试用户ID
    "mac_address": "00:50:56:c0:00:08",
    "behavior_type": "usb_copy",
    "action_detail": "U盘文件操作: 公司机密.PY",
    "file_operation": {
        "has_usb_file_op": True,
        "has_sensitive_file_op": True,
        "has_usb_write": True,  # 模拟写入
        "copied_files": ["G:\\公司机密.PY"],
        "operation_detail": "U盘文件操作: 公司机密.PY; U盘拷贝行为: 公司机密.py",
        "usb_mount_points": ["G:\\"]
    },
    "email_operation": {},
    "browser_operation": {},
    "network_type": "office",
    "is_vpn": False,
    "location_hint": "公司网络",
    "ip_address": "192.168.1.100"
}

response = requests.post(
    "http://127.0.0.1:5000/api/behavior/upload",
    json=test_data,
    headers={"Content-Type": "application/json"}
)

print("响应状态码:", response.status_code)
print("响应内容:")
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
