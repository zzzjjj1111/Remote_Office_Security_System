import platform
import psutil
import time
import json
import requests
import uuid
import random
from datetime import datetime

SERVER_URL = "http://127.0.0.1:5000/api/behavior/upload"
MOCK_MAC_ADDRESS = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0,2*6,2)][::-1])

def get_system_health():
    os_name = platform.system()
    return {
        "os_version": platform.version(),
        "antivirus_active": random.random() > 0.1,  # 简化写法
        "missing_patches": random.randint(0, 3)
    }

def collect_behavior_data():
    behavior_data = {
        "file_operations": random.randint(10, 50),
        "external_devices_connected": random.randint(0, 1),
        "screen_sharing_minutes": random.randint(0, 15) if random.random() > 0.8 else 0,
        "login_location": f"192.168.1.{random.randint(2, 254)}",
        "email_attachments_sent": random.randint(0, 5),
        "browser_visits": random.randint(50, 200)
    }

    payload = {
        "is_frontend_mock": True,
        "mock_user_id": 1,
        "mac_address": MOCK_MAC_ADDRESS,
        "behavior_type": "file_op",
        "action_detail": f"OS: {platform.system()} sync. Operations: {behavior_data['file_operations']}, Browser: {behavior_data['browser_visits']}",
        "cpu_usage": random.randint(5, 80),
        "timestamp": datetime.now().isoformat(),
        "system_health": get_system_health(),
        "behavior": behavior_data
    }
    return payload

def start_agent_loop(interval_seconds=60):
    print(f"[*] Starting Cross-Platform Remote Terminal Protection Agent on {platform.system()}...")
    print(f"[*] Agent MAC Address: {MOCK_MAC_ADDRESS}")
    print(f"[*] Target Server: {SERVER_URL}")
    print("[*] Running in user-space context. Press Ctrl+C to stop.\n")

    try:
        while True:
            data = collect_behavior_data()
            print(f"[+] Collecting multi-dimensional data... ", end="")

            try:
                # 优化：添加JSON请求头，延长超时时间
                headers = {"Content-Type": "application/json"}
                response = requests.post(
                    SERVER_URL,
                    json=data,
                    headers=headers,
                    timeout=10  # 延长超时避免误判
                )
                if response.status_code == 200:
                    # 【修复】服务器返回的是 'trust_score' 而不是 'new_trust_score'
                    score = response.json().get('trust_score', 'N/A')
                    print(f"Success! Current Trust Score: {score}")
                else:
                    # 打印服务器错误详情（调试关键）
                    err_detail = response.json().get('detail', '无详情')
                    print(f"Failed! Server returned: {response.status_code}, Detail: {err_detail}")
            except requests.exceptions.ConnectionError:
                print(f"Connection error: 无法连接服务器（请确认server.py已启动）")
            except requests.exceptions.Timeout:
                print(f"Connection error: 请求超时")
            except Exception as e:
                print(f"Connection error: {str(e)}")

            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n[*] Agent stopped by user.")

if __name__ == "__main__":
    start_agent_loop(10)