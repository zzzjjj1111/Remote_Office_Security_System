# collector.py 跨平台（Windows + macOS）完整版 补全6类核心行为采集
import os
import sys
import psutil
import time
import json
import platform
import subprocess
import threading
import argparse  # 【新增】用于解析命令行参数
import requests  # 【新增】用于HTTP请求（心跳上报、指令轮询）
from collections import deque

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    print("⚠️  警告: cryptography库未安装，将使用明文传输（生产环境请执行: pip install cryptography）")

# ===================== 【新增】极简依赖检查，无冗余报错 =====================
REQUIRED_LIBS = []
system = platform.system()
if system == "Windows":
    try:
        import win32gui
        import win32process
        import wmi
    except ImportError:
        REQUIRED_LIBS.append("pywin32 wmi")
if system == "Darwin":
    try:
        import objc
        from Foundation import NSAppleScript
    except ImportError:
        REQUIRED_LIBS.append("pyobjc")

if REQUIRED_LIBS:
    print(f"⚠️  请先安装依赖: pip install {' '.join(REQUIRED_LIBS)}")
    sys.exit(1)

# ===================== 【性能优化】全局进程缓存，消除重复遍历 =====================
_process_cache = {'data': None, 'ts': 0, 'ttl': 3}  # 进程列表缓存3秒
_patch_cache = {'val': None, 'ts': 0, 'ttl': 300}  # 补丁状态缓存5分钟
_av_cache = {'val': None, 'ts': 0, 'ttl': 300}  # 杀毒软件状态缓存5分钟
_first_cpu = True  # 首次CPU采样标记
_usb_snapshot = {}  # 【新增】U盘文件快照库，用于捕捉拷贝行为

# ===================== 【新增】AES-256加密配置（与后端behavior.py完全一致）=====================
SECRET_KEY = b'1234567890123456'  # AES密钥（16字节=AES-128，如需AES-256需32字节）
IV = b'1234567890123456'  # 初始化向量（16字节）


def encrypt_data(data_dict):
    """
    将采集的终端数据使用 AES 算法加密为 Hex 字符串
    采用 AES-CBC 模式 + PKCS7 Padding，确保传输安全
    
    Args:
        data_dict: 待加密的行为数据字典
    
    Returns:
        str: 十六进制加密字符串，失败返回None
    """
    if not ENCRYPTION_AVAILABLE:
        print("⚠️  加密模块未安装，跳过加密")
        return None
    
    try:
        # 1. JSON序列化
        json_str = json.dumps(data_dict, ensure_ascii=False)
        
        # 2. PKCS7 Padding（补齐16字节的倍数）
        pad_len = 16 - (len(json_str.encode('utf-8')) % 16)
        padded_str = json_str + chr(pad_len) * pad_len
        
        # 3. AES-CBC加密
        cipher = Cipher(algorithms.AES(SECRET_KEY), modes.CBC(IV), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_bytes = encryptor.update(padded_str.encode('utf-8')) + encryptor.finalize()
        
        # 4. 转为Hex字符串（方便HTTP传输）
        return encrypted_bytes.hex()
    except Exception as e:
        print(f"❌ 数据加密失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def _cache_get(cache_dict, fetcher):
    """通用缓存读取：过期自动刷新"""
    now = time.time()
    key = 'val' if 'val' in cache_dict else 'data'
    if cache_dict[key] is None or now - cache_dict['ts'] > cache_dict['ttl']:
        cache_dict[key] = fetcher()
        cache_dict['ts'] = now
    return cache_dict[key]


def get_cached_processes():
    """一次性获取所有进程信息，后续函数复用，避免重复遍历"""
    now = time.time()
    if _process_cache['data'] is None or now - _process_cache['ts'] > _process_cache['ttl']:
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        _process_cache['data'] = procs
        _process_cache['ts'] = now
    return _process_cache['data']


# 配置需要监控的敏感目录（添加你的敏感文件存放目录）
SENSITIVE_DIRECTORIES = [
    r"C:\Users\HP\Desktop\未公开源码_核心算法.py",     # 【新增】你提供的敏感文件所在桌面路径
    r"C:\Users\HP\Desktop\敏感文件",
    r"C:\敏感文件库",           # Windows 示例路径
    r"D:\公司机密文件",         # 可根据实际情况修改
]

# 监控间隔（秒）- 每隔多久检查一次前台窗口是否访问了敏感目录
MONITOR_INTERVAL = 2  # 每2秒检查一次

# 是否启用目录监控（True=启用, False=禁用）
ENABLE_DIRECTORY_MONITOR = True


def is_file_in_sensitive_directory(file_path):
    """
    检查文件是否在敏感目录中
    
    Args:
        file_path: 文件完整路径
    
    Returns:
        tuple: (是否敏感, 匹配的敏感目录)
    """
    if not file_path:
        return False, None
    
    file_path_lower = file_path.lower()
    
    for sensitive_dir in SENSITIVE_DIRECTORIES:
        sensitive_dir_lower = sensitive_dir.lower()
        if file_path_lower.startswith(sensitive_dir_lower):
            return True, sensitive_dir
    
    return False, None


def monitor_sensitive_file_access(behavior_data):
    """
    监控敏感文件访问（前置检测）
    在上报前先检查是否访问了敏感目录
    
    Args:
        behavior_data: 采集到的行为数据
    
    Returns:
        bool: 是否检测到敏感文件访问
    """
    if not ENABLE_DIRECTORY_MONITOR:
        return False
    
    # 从窗口标题提取文件路径
    action_detail = behavior_data.get('action_detail', '')
    file_path = None
    
    if 'WINDOW:' in action_detail:
        window_part = action_detail.split('WINDOW:')[1].strip()
        import re
        path_match = re.search(r'([A-Za-z]:\\[^\s]+\.[\w]+|/[^\s]+\.[\w]+)', window_part)
        if path_match:
            file_path = path_match.group(1)
    
    # 检查文件路径
    if file_path:
        is_sensitive, matched_dir = is_file_in_sensitive_directory(file_path)
        
        if is_sensitive:
            print(f"\n🚨 【敏感目录监控】检测到敏感文件访问！")
            print(f"   文件: {file_path}")
            print(f"   敏感目录: {matched_dir}")
            print(f"   应用: {behavior_data.get('action_detail', '').split('|')[0].replace('APP:', '').strip()}")
            
            # 立即锁定文件权限（在上报前就阻断）
            from blocker import terminal_blocker
            if os.path.exists(file_path):
                print(f"   🔒 正在锁定文件权限...")
                block_result = terminal_blocker.block_file_access(
                    file_path,
                    reason=f"敏感目录文件访问（目录：{matched_dir}）"
                )
                if block_result.get('success'):
                    print(f"   ✅ 文件已锁定")
                else:
                    print(f"   ⚠️ 文件锁定失败: {block_result.get('message')}")
            
            # 关闭标签页
            print(f"   📑 正在关闭编辑器标签页...")
            terminal_blocker.close_current_editor_tab()
            
            # 显示阻断弹窗
            print(f"   🛑 显示阻断弹窗...")
            terminal_blocker.show_blocking_overlay(
                message="敏感文件操作已被阻断",
                sub_message=f"目录: {matched_dir}\n该目录为敏感区域，禁止访问"
            )
            
            # 标记为敏感行为，触发后端告警
            behavior_data['is_sensitive'] = True
            behavior_data['sensitive_dir_monitor'] = {
                'matched': True,
                'directory': matched_dir,
                'file_path': file_path
            }
            
            return True
    
    # 不在敏感目录，不做任何标记
    return False


# ===================== 辅助函数：从行为数据中提取文件路径 =====================
def extract_file_path(behavior_data):
    """从窗口标题或操作详情中提取文件路径"""
    import re
    action_detail = behavior_data.get('action_detail', '')
    if 'WINDOW:' in action_detail:
        window_part = action_detail.split('WINDOW:')[1].strip()
        path_match = re.search(r'([A-Za-z]:\\[^\s]+\.[\w]+|/[^\s]+\.[\w]+)', window_part)
        if path_match:
            return path_match.group(1)
    return None


# ===================== 原有基础函数 =====================
def get_os_info():
    try:
        system = platform.system()
        release = platform.release()
        version = platform.version()
        if system == "Darwin":
            product = "macOS " + subprocess.getoutput("sw_vers -productVersion")
        else:
            product = f"Windows {release}"
        return {
            "os": product,
            "platform": system,
            "version": version
        }
    except:
        return {"os": "unknown", "platform": platform.system(), "version": "unknown"}


def get_device_unique_id():
    try:
        import uuid
        mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
        return ":".join([mac[i:i + 2] for i in range(0, 12, 2)])
    except:
        return "00:00:00:00:00:00"


def get_cpu_usage():
    """非阻塞CPU采样，消除每次0.5秒等待"""
    global _first_cpu
    try:
        if _first_cpu:
            psutil.cpu_percent(interval=None)
            _first_cpu = False
            return 0.0
        return round(psutil.cpu_percent(interval=None), 1)
    except:
        return 0.0


def get_usb_devices():
    try:
        system = platform.system()
        usb_list = []
        if system == "Windows":
            c = wmi.WMI()
            for item in c.Win32_USBControllerDevice():
                try:
                    usb_list.append(item.Dependent.Caption)
                except:
                    continue
        elif system == "Darwin":
            usb_raw = subprocess.getoutput("system_profiler SPUSBDataType 2>/dev/null | grep 'Product:'")
            usb_list = [line.replace("Product:", "").strip() for line in usb_raw.splitlines() if "Product:" in line]
        return usb_list[:3]
    except:
        return []


def get_patch_status():
    try:
        def _fetch():
            system = platform.system()
            if system == "Windows":
                c = wmi.WMI()
                hotfixes = c.Win32_QuickFixEngineering()
                if not hotfixes:
                    return "严重落后"
                from datetime import datetime
                recent_updates = []
                for hf in hotfixes:
                    if hf.InstalledOn:
                        try:
                            install_date = datetime.strptime(hf.InstalledOn, '%m/%d/%Y')
                            if (datetime.now() - install_date).days <= 90:
                                recent_updates.append(hf)
                        except:
                            continue
                if len(recent_updates) >= 3:
                    return "已更新"
                elif len(recent_updates) >= 1:
                    return "缺失关键补丁"
                else:
                    return "严重落后"
            elif system == "Darwin":
                current_version = subprocess.getoutput("sw_vers -productVersion").strip()
                version_parts = current_version.split('.')
                if len(version_parts) >= 2:
                    major = int(version_parts[0])
                    minor = int(version_parts[1])
                    if major >= 14:
                        return "已更新"
                    elif major == 13 and minor >= 5:
                        return "缺失关键补丁"
                    else:
                        return "严重落后"
                return "已更新"
            return "未知"

        return _cache_get(_patch_cache, _fetch)
    except Exception as e:
        return "未知"


def get_antivirus_status():
    try:
        def _fetch():
            system = platform.system()
            if system == "Windows":
                common_av = {
                    'msmpeng.exe': 'Windows Defender',
                    '360tray.exe': '360安全卫士',
                    'QQPCRTP.exe': '腾讯电脑管家',
                    'kxescore.exe': '金山毒霸',
                    'avp.exe': '卡巴斯基',
                    'egui.exe': 'NOD32'
                }
                procs = get_cached_processes()
                for p in procs:
                    pname = (p.get('name') or '').lower()
                    for av_proc, av_name in common_av.items():
                        if av_proc.lower() in pname:
                            return f"{av_name} 正常"
                    if 'defender' in pname or 'msmpeng' in pname:
                        return "Windows Defender 正常"
                return "未安装/未运行"
            elif system == "Darwin":
                av_apps = [
                    '/Applications/ClamXAV.app',
                    '/Applications/Sophos Endpoint.app',
                    '/Applications/McAfee Endpoint Security.app',
                    '/Applications/Bitdefender.app'
                ]
                for app_path in av_apps:
                    if os.path.exists(app_path):
                        app_name = os.path.basename(app_path).replace('.app', '')
                        return f"{app_name} 正常"
                xprotect_status = subprocess.getoutput(
                    "defaults read /Library/Apple/System/Library/LaunchDaemons/com.apple.XProtect.daemon 2>/dev/null | grep -c 'Disable'"
                )
                if xprotect_status.strip() == '0' or xprotect_status.strip() == '':
                    return "XProtect 正常"
                return "未安装/未运行"
            return "未知"

        return _cache_get(_av_cache, _fetch)
    except Exception as e:
        return "未知"


def get_network_context():
    try:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        # 【优化】公网 IP 缓存机制：5 分钟内不重复请求，解决网络卡顿
        if not hasattr(get_network_context, '_cached_public_ip') or \
                time.time() - get_network_context._cache_time > 300:
            try:
                import requests
                get_network_context._cached_public_ip = requests.get('https://api.ipify.org', timeout=2).text.strip()
                get_network_context._cache_time = time.time()
            except:
                get_network_context._cached_public_ip = local_ip

        public_ip = get_network_context._cached_public_ip
        is_vpn = False
        vpn_indicators = ['tun', 'tap', 'ppp', 'vpn', 'openvpn', 'wireguard']
        system = platform.system()
        if system == "Windows":
            c = wmi.WMI()
            for interface in c.Win32_NetworkAdapterConfiguration(IPEnabled=True):
                if interface.Description:
                    desc_lower = interface.Description.lower()
                    if any(vpn in desc_lower for vpn in vpn_indicators):
                        is_vpn = True
                        break
        elif system == "Darwin":
            network_output = subprocess.getoutput("ifconfig | grep -i 'utun\\|ppp\\|vpn'")
            if network_output:
                is_vpn = True
        network_type = 'unknown'
        location_hint = '未知位置'
        if is_vpn:
            network_type = 'vpn'
            location_hint = 'VPN连接'
        elif local_ip.startswith('192.168.') or local_ip.startswith('10.'):
            if local_ip.startswith('192.168.1.'):
                network_type = 'office'
                location_hint = '公司网络'
            else:
                network_type = 'home'
                location_hint = '家庭网络'
        else:
            network_type = 'mobile'
            location_hint = '移动网络/异地'
        return {
            'ip_address': public_ip,
            'local_ip': local_ip,
            'is_vpn': is_vpn,
            'network_type': network_type,
            'location_hint': location_hint
        }
    except Exception as e:
        return {
            'ip_address': 'unknown',
            'local_ip': 'unknown',
            'is_vpn': False,
            'network_type': 'unknown',
            'location_hint': '检测失败'
        }


def get_screen_sharing_status():
    try:
        system = platform.system()
        screen_share_apps = {
            'teams.exe': ('Microsoft Teams', '视频会议'),
            'zoom.exe': ('Zoom', '视频会议'),
            'tencentmeeting.exe': ('腾讯会议', '视频会议'),
            'feishu.exe': ('飞书', '视频会议'),
            'dingtalk.exe': ('钉钉', '视频会议'),
            'anydesk.exe': ('AnyDesk', '远程控制'),
            'teamviewer.exe': ('TeamViewer', '远程控制'),
            'mstsc.exe': ('远程桌面', '远程控制'),
        }
        # 【优化】使用缓存进程列表，避免重复遍历
        procs = get_cached_processes()
        for p in procs:
            try:
                proc_name = (p.get('name') or '').lower()
                for app_key, (app_name, share_type) in screen_share_apps.items():
                    if app_key in proc_name:
                        # 只对匹配的进程获取cmdline
                        try:
                            proc = psutil.Process(p['pid'])
                            cmdline = ' '.join(proc.cmdline()).lower() if proc.cmdline() else ''
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                        sharing_indicators = ['share', 'screen', 'present', 'meeting']
                        if any(indicator in cmdline for indicator in sharing_indicators):
                            return {
                                'is_sharing': True,
                                'app_name': app_name,
                                'sharing_type': share_type
                            }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if system == "Windows":
            try:
                c = wmi.WMI()
                for session in c.Win32_LogonSession():
                    if session.LogonType == 10:
                        return {
                            'is_sharing': True,
                            'app_name': '远程桌面',
                            'sharing_type': '远程控制'
                        }
            except:
                pass
        elif system == "Darwin":
            try:
                sharing_check = subprocess.getoutput(
                    "osascript -e 'tell application \"System Events\" to get name of every process whose visible is true' 2>/dev/null | grep -i 'share\\|screen'"
                )
                if sharing_check:
                    return {
                        'is_sharing': True,
                        'app_name': 'macOS屏幕共享',
                        'sharing_type': '系统共享'
                    }
            except:
                pass
        return {
            'is_sharing': False,
            'app_name': None,
            'sharing_type': None
        }
    except Exception as e:
        return {
            'is_sharing': False,
            'app_name': None,
            'sharing_type': None
        }


# ===================== 【新增】真实维度数据采集引擎 =====================

def get_real_location():
    """1. 真实物理位置采集 (基于 IP 的地理围栏)"""
    try:
        import requests
        # 调用免费接口获取当前设备的公网IP和真实物理城市
        resp = requests.get('http://ip-api.com/json/?lang=zh-CN', timeout=3).json()
        if resp['status'] == 'success':
            return f"{resp['regionName']}{resp['city']} (公网IP: {resp['query']})"
    except:
        pass
    return "局域网/内网环境 (无法精确定位)"

def get_real_health_status():
    """2. 真实设备健康数据 (查杀软与系统补丁)"""
    av_status = "未安装/未运行"
    patch_status = "未更新"
    try:
        if platform.system() == "Windows":
            import wmi
            # 调取 Windows 安全中心底层接口 (WMI) 查杀毒软件
            c = wmi.WMI(namespace="root\\SecurityCenter2")
            av_products = c.AntivirusProduct()
            if av_products:
                av_status = f"正常运行 ({av_products[0].displayName})"
            
            # 调取 Windows 系统更新接口查最新补丁
            w = wmi.WMI()
            qfes = w.Win32_QuickFixEngineering()
            if qfes:
                patch_status = f"已更新 (最新补丁: {qfes[0].HotFixID})"
    except Exception as e:
        pass
    return patch_status, av_status

def check_real_screen_sharing():
    """3. 真实屏幕共享与远程控制检测（增强版）"""
    share_apps = {
        'wemeetapp.exe': ('腾讯会议', '视频会议'),
        'ToDesk.exe': ('ToDesk', '远程控制'),
        'TeamViewer.exe': ('TeamViewer', '远程控制'),
        'SunloginClient.exe': ('向日葵', '远程控制'),
        'DingTalk.exe': ('钉钉', '视频会议')
    }
    try:
        # 遍历当前系统所有正在运行的进程
        for proc in psutil.process_iter(['name', 'status']):
            name = proc.info['name']
            if name and name in share_apps:
                app_name, app_type = share_apps[name]
                
                # 【核心修复】增加二次验证：检查进程是否有网络连接或前台窗口
                try:
                    p = psutil.Process(proc.pid)
                    
                    # 验证1：检查是否有网络连接（远程控制必须有网络活动）
                    connections = p.net_connections()
                    has_network = len(connections) > 0
                    
                    # 验证2：检查进程状态是否为running（排除僵尸进程）
                    is_running = p.status() == psutil.STATUS_RUNNING
                    
                    # 验证3：对于远程控制软件，检查是否有前台窗口
                    has_foreground = False
                    import platform
                    system = platform.system()
                    if system == "Windows":
                        import ctypes
                        try:
                            hwnd = ctypes.windll.user32.GetForegroundWindow()
                            pid = ctypes.c_ulong()
                            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                            has_foreground = (pid.value == proc.pid)
                        except:
                            pass
                    
                    # 【判定逻辑】满足以下任一条件才认为是真实的远程控制：
                    # 1. 有网络连接 + 正在运行
                    # 2. 有前台窗口
                    if (has_network and is_running) or has_foreground:
                        print(f"✅ [远程控制验证通过] {app_name} (PID:{proc.pid}, 网络:{has_network}, 前台:{has_foreground})")
                        return True, app_name, app_type
                    else:
                        print(f"⚠️ [远程控制误报过滤] {app_name} 进程存在但无活动 (PID:{proc.pid})")
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
    except Exception as e:
        print(f"⚠️ [远程控制检测] 异常: {e}")
        pass
    return False, "无", "无"

def analyze_window_for_email_and_browser(app_name, window_title):
    """4. 真实浏览器与邮件行为推断 (基于智能窗口语义分析)"""
    email_op = {'send_detail': '无邮件外发操作', 'has_email_op': False}
    browser_op = {'active_tab_title': '未知', 'has_browser_op': False}
    
    title_lower = window_title.lower()
    
    # 浏览器行为检测
    browsers = ['chrome', 'edge', 'firefox', 'safari', '浏览器']
    if any(b in app_name.lower() or b in title_lower for b in browsers):
        browser_op['has_browser_op'] = True
        browser_op['active_tab_title'] = window_title.replace('- Google Chrome', '').replace('- Microsoft Edge', '').strip()
    
    # 邮件行为检测 (Foxmail, Outlook, 或网页版邮箱)
    if 'mail' in app_name.lower() or 'outlook' in app_name.lower() or '邮箱' in title_lower:
        email_op['has_email_op'] = True
        if '写信' in title_lower or '发送' in title_lower or '新建邮件' in title_lower:
            email_op['send_detail'] = f"正在编辑外发邮件: {window_title}"
        elif '附件' in title_lower:
            email_op['send_detail'] = f"检测到邮件附件操作: {window_title}"
        else:
            email_op['send_detail'] = f"正在使用邮件客户端"
            
    return email_op, browser_op
# =====================================================================

# ===================== 补全3类核心行为采集（性能优化版）=====================
# 1. 【核心补全+性能优化】文件操作采集
def get_file_operation_info():
    """
    极简文件操作采集：仅检查关键进程的 open_files()，不再遍历所有进程
    这是解决 30-80 秒延迟的核心修改
    """
    try:
        system = platform.system()
        file_ops = []
        sensitive_keywords = ['源码', '源代码', '财务报表', '客户信息', '合同', '核心数据', 'secret', 'confidential']
        usb_mount_points = []

        # 步骤1：识别外接存储/U盘挂载点（WMI + psutil 双保险）
        if system == "Windows":
            # 方案A：psutil 快速检测（不需要WMI，速度快且稳定）
            for part in psutil.disk_partitions():
                # Windows 可移动磁盘的 opts 通常包含 'removable'
                if 'removable' in part.opts.lower() or part.fstype == 'FAT' or part.fstype == 'FAT32':
                    usb_mount_points.append(part.device + "\\")
                    print(f"💾 [USB检测-psutil] 发现可移动磁盘: {part.device} ({part.fstype})")

            # 方案B：WMI 补充检测（psutil 可能漏掉刚插入的U盘）
            try:
                c = wmi.WMI()
                for disk in c.Win32_LogicalDisk(DriveType=2):
                    dev = disk.DeviceID + "\\"
                    if dev not in usb_mount_points:
                        usb_mount_points.append(dev)
                        print(f"💾 [USB检测-WMI] 发现可移动磁盘: {disk.DeviceID}")
            except Exception as wmi_err:
                print(f"⚠️ [USB检测] WMI 查询失败({wmi_err})，仅使用 psutil 结果")

            if not usb_mount_points:
                print(f"💾 [USB检测] 未检测到任何可移动磁盘")

        elif system == "Darwin":
            mount_raw = subprocess.getoutput("mount | grep -i /Volumes/ | grep -v /System/Volumes")
            for line in mount_raw.splitlines():
                if line.strip():
                    try:
                        mount_path = line.split(' on ')[1].split(' (')[0]
                        usb_mount_points.append(mount_path)
                    except:
                        pass

        # ====== 【新增】U盘文件快照比对法（精准捕捉拷贝动作） ======
        global _usb_snapshot
        copied_files_to_usb = []
        for mount in usb_mount_points:
            current_files = {}
            try:
                # 仅扫描两层目录，防止U盘太大导致电脑卡顿
                for root_dir, dirs, files in os.walk(mount):
                    if root_dir.count(os.sep) - mount.count(os.sep) > 1:
                        del dirs[:]
                        continue
                    for f in files:
                        fpath = os.path.join(root_dir, f)
                        try:
                            current_files[fpath] = os.path.getmtime(fpath)
                        except:
                            pass

                if mount in _usb_snapshot:
                    old_files = _usb_snapshot[mount]
                    for fpath, mtime in current_files.items():
                        # 如果发现新文件，或者文件被修改
                        if fpath not in old_files or mtime > old_files.get(fpath, 0):
                            copied_files_to_usb.append(fpath)
                            file_ops.append(f"U盘拷贝行为: {os.path.basename(fpath)}")

                _usb_snapshot[mount] = current_files
            except Exception as e:
                pass
        # =======================================================


        # 步骤2：【性能优化】仅检查文件管理器/IDE/Office等关键进程
        key_process_names = [
            'explorer.exe', 'pycharm64.exe', 'code.exe', 'devenv.exe',
            'wps.exe', 'et.exe', 'winword.exe', 'excel.exe', 'powerpnt.exe',
            'finder', 'terminal.exe', 'cmd.exe', 'powershell.exe',
            'notepad.exe', 'notepad++.exe', 'sublime_text.exe', 'python.exe'
        ]

        procs = get_cached_processes()
        for p in procs:
            pname = (p.get('name') or '').lower()
            if not any(kn in pname for kn in key_process_names):
                continue  # 跳过非关键进程，大幅减少 open_files 调用

            try:
                proc = psutil.Process(p['pid'])
                open_files = proc.open_files()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            for f in open_files:
                fpath = f.path
                # 检测U盘文件操作
                for mount in usb_mount_points:
                    if mount.lower() in fpath.lower():
                        file_ops.append(f"U盘文件操作: {os.path.basename(fpath)}")
                # 检测敏感文件访问
                for keyword in sensitive_keywords:
                    if keyword in fpath.lower():
                        file_ops.append(f"敏感文件访问: {os.path.basename(fpath)}")
                if len(file_ops) >= 5:
                    break
            if len(file_ops) >= 5:
                break

        if not file_ops and usb_mount_points:
            file_ops.append(f"检测到外接存储: {', '.join(usb_mount_points)}")

        file_ops = list(set(file_ops))[:5]
        
        # 【修复】USB检测逻辑：只要有USB挂载点就标记为USB操作
        has_usb_detected = len(usb_mount_points) > 0
        has_usb_file_operation = len([x for x in file_ops if 'U盘' in x]) > 0
        
        return {
            'has_usb_file_op': has_usb_detected or has_usb_file_operation,  # 只要检测到USB设备就标记
            'has_sensitive_file_op': len([x for x in file_ops if '敏感文件' in x]) > 0,
            'has_usb_write': len(copied_files_to_usb) > 0,  # 是否检测到精准的写入拷贝
            'copied_files': copied_files_to_usb,  # 拷贝进去的具体文件路径
            'operation_detail': '; '.join(file_ops) if file_ops else '无文件操作',
            'usb_mount_points': usb_mount_points
        }
    except Exception as e:
        print(f"❌ [USB检测] get_file_operation_info 崩溃: {e}")
        import traceback
        traceback.print_exc()
        return {
            'has_usb_file_op': False,
            'has_sensitive_file_op': False,
            'operation_detail': f'采集失败: {str(e)}',
            'usb_mount_points': []
        }


# 2. 【核心补全+性能优化】邮件附件发送采集
def get_email_attachment_info():
    """
    极简邮件附件发送采集：使用缓存进程列表 + SMTP启发式检测
    """
    try:
        email_clients = ['outlook.exe', 'foxmail.exe', 'thunderbird.exe', 'mail.app', 'spark.exe']
        is_email_client_running = False
        has_smtp_connection = False
        attachment_op = False

        # 使用缓存进程列表检测邮件客户端
        procs = get_cached_processes()
        for p in procs:
            pname = (p.get('name') or '').lower()
            for client in email_clients:
                if client.lower() in pname:
                    is_email_client_running = True
                    break
            if is_email_client_running:
                break

        # 检测SMTP外发连接
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'ESTABLISHED' and conn.raddr:
                    if conn.raddr.port in [25, 465, 587]:
                        has_smtp_connection = True
                        break
        except psutil.AccessDenied:
            pass

        # 启发式：邮件客户端运行 + SMTP连接 = 高概率附件操作
        if is_email_client_running and has_smtp_connection:
            attachment_op = True

        return {
            'email_client_running': is_email_client_running,
            'is_sending_email': has_smtp_connection,
            'has_attachment_operation': attachment_op,
            'send_detail': '检测到邮件附件外发操作' if (has_smtp_connection and attachment_op) else '无邮件外发操作'
        }
    except Exception as e:
        return {
            'email_client_running': False,
            'is_sending_email': False,
            'has_attachment_operation': False,
            'send_detail': f'采集失败: {str(e)}'
        }


# 3. 【核心补全】浏览器访问采集（复用现有窗口采集逻辑，无冗余）
def get_browser_visit_info():
    """
    极简浏览器访问采集：获取当前活跃浏览器的标签页标题/URL
    完全复用现有前台窗口采集逻辑，跨平台兼容，无冗余代码
    """
    try:
        system = platform.system()
        browser_list = ['chrome.exe', 'msedge.exe', 'firefox.exe', 'safari', 'brave.exe']
        is_browser_active = False
        active_browser = None
        active_tab_title = "未知"
        active_tab_url = "未知"

        # 先通过现有窗口函数获取前台应用
        app_name, window_title = get_active_window_and_app()
        app_name_lower = app_name.lower()

        # 检测是否为浏览器
        for browser in browser_list:
            if browser.split('.')[0].lower() in app_name_lower:
                is_browser_active = True
                active_browser = browser.split('.')[0]
                active_tab_title = window_title
                break

        # 进阶获取URL（跨平台极简实现）
        if is_browser_active and system == "Darwin":
            try:
                script = f'''
                tell application "{active_browser}"
                    set currentTab to active tab of front window
                    set tabURL to URL of currentTab
                    return tabURL
                end tell
                '''
                url_result = subprocess.getoutput(f"osascript -e '{script}'")
                if url_result and not url_result.startswith('execution error'):
                    active_tab_url = url_result.strip()
            except:
                pass

        return {
            'is_browser_active': is_browser_active,
            'browser_name': active_browser,
            'active_tab_title': active_tab_title,
            'active_tab_url': active_tab_url
        }
    except Exception as e:
        return {
            'is_browser_active': False,
            'browser_name': None,
            'active_tab_title': f'采集失败: {str(e)}',
            'active_tab_url': '未知'
        }


def _determine_behavior_type(app, title, file_op_info, email_info, browser_info, screen_share_info, usb_devices):
    """
    【核心修复】根据实际检测到的行为类型动态设置 behavior_type
    
    优先级（从高到低）：
    1. 屏幕共享 (screen_sharing)
    2. USB拷贝 (usb_copy)
    3. 邮件发送 (email_send)
    4. 浏览器访问 (browser_visit)
    5. 文件操作 (file_access)
    6. 普通窗口活动 (window_activity)
    7. 空闲状态 (idle)
    """
    # 0. 空闲状态
    if app == "Unknown":
        return "idle"
    
    # 1. 屏幕共享检测（最高优先级）
    if screen_share_info.get('is_sharing'):
        share_type = screen_share_info.get('sharing_type', '未知')
        if share_type == '远程控制':
            return "remote_control_sharing"
        elif share_type == '系统共享':
            return "system_screen_sharing"
        else:
            return "video_conference_sharing"
    
    # 2. USB设备操作检测
    file_op = file_op_info or {}
    has_usb_write = file_op.get('has_usb_write', False)
    has_usb_file_op = file_op.get('has_usb_file_op', False)
    copied_files = file_op.get('copied_files', [])
    
    if has_usb_write or len(copied_files) > 0:
        return "usb_copy"  # U盘写入/拷贝
    elif has_usb_file_op:
        return "usb_access"  # U盘访问但未写入
    
    # 3. 邮件发送检测
    email_op = email_info or {}
    if email_op.get('has_email_op'):
        send_detail = email_op.get('send_detail', '')
        if '附件' in send_detail or 'attachment' in send_detail.lower():
            return "email_with_attachment"
        return "email_send"
    
    # 4. 浏览器访问检测
    browser_op = browser_info or {}
    if browser_op.get('has_browser_op'):
        tab_title = browser_op.get('active_tab_title', '').lower()
        # 检查是否为敏感网站
        sensitive_sites = ['github', 'gitee', 'gitlab', 'baidu.com', 'weibo']
        if any(site in tab_title for site in sensitive_sites):
            return "sensitive_website_visit"
        return "browser_visit"
    
    # 5. 文件操作检测
    if file_op.get('has_sensitive_file_op'):
        return "sensitive_file_access"
    
    operation_detail = file_op.get('operation_detail', '无文件操作')
    if operation_detail != '无文件操作':
        # 检查是否涉及敏感目录
        sensitive_dirs = ['机密', '秘密', '财务', '人事', 'confidential', 'secret']
        if any(d in operation_detail.lower() for d in sensitive_dirs):
            return "sensitive_directory_access"
        return "file_access"
    
    # 6. 默认：普通窗口活动
    return "window_activity"


# ===================== 原有窗口采集函数 =====================
def get_active_window_and_app():
    try:
        system = platform.system()
        app_name = "Unknown"
        window_title = "Unknown"
        if system == "Windows":
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                window_title = win32gui.GetWindowText(hwnd)
                tid, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    proc = psutil.Process(pid)
                    app_name = proc.name()
                except:
                    app_name = "Unknown"
        elif system == "Darwin":
            app_name = subprocess.getoutput(
                "osascript -e 'tell application \"System Events\" to get name of first application process whose frontmost is true'"
            ).strip()
            window_title = subprocess.getoutput(
                "osascript -e 'tell application \"System Events\" to get title of first window of first application process whose frontmost is true'"
            ).strip()
            if window_title == "": window_title = app_name
        return app_name, window_title
    except:
        return "Unknown", "Unknown"


# ===================== 主采集函数 =====================
def collect_behavior():
    """
    对外主函数：补全6类核心行为采集，完全兼容原有后端接口
    """
    # 【性能】提前预热CPU采样（消除首次阻塞）
    global _first_cpu
    if _first_cpu:
        psutil.cpu_percent(interval=None)
        _first_cpu = False

    start_time = time.time()

    app, title = get_active_window_and_app()
    print(f"👀 [Agent] 当前前台窗口: {title}")

    # 【优化】优先检测窗口标题（极速响应，不依赖耗时的进程扫描）
    sensitive_keywords = ['财务报表', '客户名单', '薪资', '源码', '机密', 'confidential', 'secret', '未公开']
    is_window_sensitive = any(k in title for k in sensitive_keywords)

    # ======== 【核心修复 1】U盘插入和后台拷贝不能被前台窗口屏蔽！ ========
    # 必须每次都调用 get_file_operation_info() 维持 U盘快照更新
    file_op_info = get_file_operation_info()

    if is_window_sensitive:
        print(f"👁️ [Agent] 窗口标题命中敏感词: {title}")
        file_op_info['has_sensitive_file_op'] = True
        if file_op_info['operation_detail'] == '无文件操作':
            file_op_info['operation_detail'] = f"敏感窗口访问: {title}"
        else:
            file_op_info['operation_detail'] = f"敏感窗口访问: {title}; " + file_op_info['operation_detail']
    # ======================================================================

    network_ctx = get_network_context()
    usb_devices = get_usb_devices()  # 【优化】只调用一次，避免重复
    
    # 新增3类核心行为采集
    email_info = get_email_attachment_info()
    browser_info = get_browser_visit_info()
    screen_share_info = get_screen_sharing_status()
    
    # 【增强】使用真实检测引擎补充数据
    try:
        # 1. 真实位置信息（补充网络上下文）
        real_location = get_real_location()
        if '公网IP' in real_location:
            network_ctx['real_location'] = real_location
        
        # 2. 真实健康状态（补充补丁和杀毒软件信息）
        patch, av = get_real_health_status()
        if patch != "未更新":
            network_ctx['real_patch_status'] = patch
        if av != "未安装/未运行":
            network_ctx['real_av_status'] = av
        
        # 3. 真实屏幕共享检测（二次验证）
        is_sharing, share_app, share_type = check_real_screen_sharing()
        if is_sharing and not screen_share_info.get('is_sharing'):
            print(f"🔍 [真实检测] 发现屏幕共享: {share_app} ({share_type})")
            screen_share_info = {
                'is_sharing': True,
                'app_name': share_app,
                'sharing_type': share_type
            }
        
        # 4. 窗口语义分析（增强邮件和浏览器检测）
        enhanced_email, enhanced_browser = analyze_window_for_email_and_browser(app, title)
        if enhanced_email['has_email_op']:
            email_info['send_detail'] = enhanced_email['send_detail']
            email_info['has_email_op'] = True
        if enhanced_browser['has_browser_op']:
            browser_info['active_tab_title'] = enhanced_browser['active_tab_title']
            browser_info['has_browser_op'] = True
    except Exception as e:
        print(f"⚠️ 真实检测引擎异常: {e}")

    # 【核心修复】根据实际检测到的行为类型设置不同的behavior_type
    # 优先级：屏幕共享 > USB操作 > 邮件发送 > 浏览器访问 > 文件操作 > 普通窗口活动
    behavior_type = _determine_behavior_type(
        app=app,
        title=title,
        file_op_info=file_op_info,
        email_info=email_info,
        browser_info=browser_info,
        screen_share_info=screen_share_info,
        usb_devices=usb_devices
    )

    behavior_data = {
        "mac_address": get_device_unique_id(),
        "behavior_type": behavior_type,
        "action_detail": f"APP:{app} | WINDOW:{title}",
        "cpu_usage": get_cpu_usage(),
        "os_info": get_os_info(),
        "usb_devices": usb_devices,  # 【优化】使用缓存变量
        "timestamp": int(time.time()),
        "patch_status": get_patch_status(),
        "antivirus_status": get_antivirus_status(),
        "ip_address": network_ctx['ip_address'],
        "is_vpn": network_ctx['is_vpn'],
        "network_type": network_ctx['network_type'],
        "location_hint": network_ctx['location_hint'],
        "upload_id": f"{get_device_unique_id()}_{int(time.time())}_{os.urandom(4).hex()}",
        "file_operation": file_op_info,
        "email_operation": email_info,
        "browser_operation": browser_info,
        "screen_share": screen_share_info,
        "login_location": network_ctx,
        "external_device": usb_devices  # 【优化】使用缓存变量，避免重复调用
    }

    elapsed = time.time() - start_time
    print(f"⏱️ [Agent] 采集耗时: {elapsed:.2f} 秒")
    return behavior_data


# ===================== 断点续传模块 =====================
class BehaviorUploadQueue:
    def __init__(self, max_queue_size=1000, cache_file="upload_cache.json"):
        self.queue = deque(maxlen=max_queue_size)
        self.cache_file = cache_file
        self.is_uploading = False
        self.max_retries = 5
        self.base_delay = 2
        self._load_cache()

    def add(self, behavior_data):
        behavior_data['retry_count'] = 0
        behavior_data['last_error'] = None
        self.queue.append(behavior_data)
        print(f"📦 数据已加入上传队列，当前队列大小: {len(self.queue)}")

    def _load_cache(self):
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                for item in cached_data:
                    if 'retry_count' not in item:
                        item['retry_count'] = 0
                    self.queue.append(item)
                print(f"📂 加载历史缓存: {len(cached_data)} 条数据")
        except Exception as e:
            print(f"⚠️ 加载缓存失败: {e}")

    def _save_cache(self):
        try:
            data_to_save = list(self.queue)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存缓存失败: {e}")

    def upload_with_retry(self, behavior_data, server_url):
        import requests
        for attempt in range(self.max_retries):
            try:
                # ===================== 【核心修改】AES-256加密传输 =====================
                # 移除内部字段，只加密业务数据
                data_to_encrypt = {k: v for k, v in behavior_data.items() if k not in ['mock_user_id', 'retry_count', 'last_error']}
                
                # 执行AES加密
                encrypted_hex = encrypt_data(data_to_encrypt)
                
                if encrypted_hex:
                    # 加密成功：发送密文
                    payload = {
                        "encrypted_data": encrypted_hex,
                        "mock_user_id": behavior_data.get("mock_user_id", 1)  # 用户ID明文（用于路由）
                    }
                    print(f"🔐 [加密传输] 数据已加密，密文长度: {len(encrypted_hex)} 字符")
                else:
                    # 加密失败或未安装库：降级为明文（兼容开发环境）
                    payload = {
                        "is_frontend_mock": True,
                        "mock_user_id": behavior_data.get("mock_user_id", 1),
                        **data_to_encrypt
                    }
                    print(f"⚠️  [明文传输] 加密不可用，使用明文（生产环境请安装cryptography）")
                # ===================================================================
                
                response = requests.post(
                    server_url,
                    json=payload,
                    timeout=15
                )
                
                # 【修复】检查HTTP状态码和响应内容
                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    print(f"❌ 服务器返回错误: {error_msg}")
                    behavior_data['last_error'] = error_msg
                    raise Exception(error_msg)
                
                # 检查响应是否为JSON
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    error_msg = f"非JSON响应 (Content-Type: {content_type}): {response.text[:200]}"
                    print(f"❌ {error_msg}")
                    behavior_data['last_error'] = error_msg
                    raise Exception(error_msg)
                
                result = response.json()
                print(f"✅ 上传成功 | ID: {behavior_data.get('upload_id', 'N/A')[:12]}... | "
                      f"状态: {result.get('status')} | 操作: {result.get('action', 'pass')}")
                return True
            except requests.exceptions.Timeout:
                error_msg = f"超时 (尝试 {attempt + 1}/{self.max_retries})"
                print(f"⏱️ {error_msg}")
                behavior_data['last_error'] = error_msg
            except requests.exceptions.ConnectionError:
                error_msg = f"连接失败 (尝试 {attempt + 1}/{self.max_retries})"
                print(f"🔌 {error_msg}")
                behavior_data['last_error'] = error_msg
            except Exception as e:
                error_msg = f"异常: {str(e)} (尝试 {attempt + 1}/{self.max_retries})"
                print(f"❌ {error_msg}")
                behavior_data['last_error'] = error_msg
            if attempt < self.max_retries - 1:
                delay = self.base_delay * (2 ** attempt)
                print(f"⏳ 等待 {delay} 秒后重试...")
                time.sleep(delay)
        print(f"❌ 上传最终失败: {behavior_data.get('upload_id', 'N/A')[:12]}...")
        return False

    def process_queue(self, server_url):
        if self.is_uploading or len(self.queue) == 0:
            return
        self.is_uploading = True
        print(f"\n{'=' * 60}")
        print(f"🚀 开始处理上传队列，待上传: {len(self.queue)} 条")
        print(f"{'=' * 60}")
        success_count = 0
        failed_count = 0
        items_to_process = list(self.queue)
        for behavior_data in items_to_process:
            if behavior_data.get('retry_count', 0) >= self.max_retries:
                print(f"⚠️ 跳过已超过最大重试次数的数据: {behavior_data.get('upload_id', 'N/A')[:12]}...")
                self.queue.remove(behavior_data)
                failed_count += 1
                continue
            success = self.upload_with_retry(behavior_data, server_url)
            if success:
                self.queue.remove(behavior_data)
                success_count += 1
            else:
                behavior_data['retry_count'] = behavior_data.get('retry_count', 0) + 1
                failed_count += 1
                print(f"🔄 数据将保留在队列中，下次继续尝试 (重试次数: {behavior_data['retry_count']})")
        self._save_cache()
        print(f"\n{'=' * 60}")
        print(f"📊 上传队列处理完成")
        print(f"   ✅ 成功: {success_count} 条")
        print(f"   ❌ 失败: {failed_count} 条")
        print(f"   📦 剩余: {len(self.queue)} 条")
        print(f"{'=' * 60}\n")
        self.is_uploading = False

    def get_queue_status(self):
        return {
            'queue_size': len(self.queue),
            'is_uploading': self.is_uploading,
            'cache_file': self.cache_file
        }


# ===================== 全局实例、上报函数、启动函数 =====================
upload_queue = BehaviorUploadQueue(max_queue_size=1000, cache_file="upload_cache.json")


def send_behavior_to_server(behavior_data, server_url="http://127.0.0.1:5000/api/behavior/upload"):
    try:
        import requests
        
        # 【新增】前置检测：敏感目录监控
        if ENABLE_DIRECTORY_MONITOR:
            sensitive_detected = monitor_sensitive_file_access(behavior_data)
            if sensitive_detected:
                print(f"   📡 立即上报敏感目录访问事件...")
                # 继续上报，让后端记录告警
        payload = {
            "is_frontend_mock": True,
            "mock_user_id": behavior_data.get("mock_user_id", 1),
            **{k: v for k, v in behavior_data.items() if k not in ['mock_user_id']}
        }
        response = requests.post(server_url, json=payload, timeout=15)
        
        # 【修复】检查HTTP状态码和响应内容
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 服务器返回错误: {error_msg}")
            raise Exception(error_msg)
        
        # 检查响应是否为JSON
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' not in content_type:
            error_msg = f"非JSON响应 (Content-Type: {content_type}): {response.text[:200]}"
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {error_msg}")
            raise Exception(error_msg)
        
        result = response.json()

        # 【新增】处理二次确认请求
        if result.get('action') == 'confirm_required':
            print(f"\n🔔 收到二次确认请求：{result.get('message')}")

            from blocker import terminal_blocker
            target_file = result.get('file_path') or extract_file_path(behavior_data)

            # 提取纯文件名用于精准锁定窗口
            pure_filename = os.path.basename(target_file) if target_file else result.get('file_name', '未知')

            # ======== 【核心修改】先物理隔离，再审批 ========
            print(f"   🛑 正在启动物理隔离黑屏以等待安全确认...")
            terminal_blocker.close_current_editor_tab()
            if target_file and os.path.exists(target_file):
                terminal_blocker.block_file_access(target_file, reason="等待二次确认授权")

            terminal_blocker.start_persistent_black_screen(
                forbidden_title=pure_filename,
                trigger_reason=result.get('trigger_reason', 'anomaly_behavior')
            )
            # ==========================================

            # 此时文件已被黑屏挡住，再弹出选择框
            # 【核心修改】获取后端的 trust_score 并传给弹窗组件
            trust_score = result.get('trust_score', 100)
            decision = terminal_blocker.show_confirmation_dialog(
                file_name=result.get('file_name', '未知文件'),
                operation_type=result.get('operation', '文件操作'),
                sensitive_words=result.get('sensitive_words', []),
                trust_score=trust_score,
                trigger_reason=result.get('trigger_reason', 'anomaly_behavior')
            )

            # 上报决策
            log_id = result.get('log_id')
            user_id = behavior_data.get('mock_user_id', 1)

            try:
                decision_response = requests.post(
                    'http://127.0.0.1:5000/api/alerts/decision',
                    json={'log_id': log_id, 'user_id': user_id, 'decision': decision},
                    timeout=10
                )
                decision_result = decision_response.json()
                print(f"✅ 决策已上报：{decision} -> {decision_result.get('message')}")

                # ======== 【核心修改】根据决策处理黑屏状态 ========
                if decision == 'allow':
                    print(f"   🔓 确认合规操作，解除物理隔离黑屏。")
                    terminal_blocker.stop_persistent_black_screen()
                    if target_file and os.path.exists(target_file):
                        terminal_blocker.restore_file_access(target_file)

                elif decision == 'block':
                    # 【点击取消】
                    print(f"   🔒 拒绝授权！操作已取消，解除黑屏。")

                    # 【重要】用户点击取消后，停止当前黑屏
                    terminal_blocker.stop_persistent_black_screen()

                    # 【新增】如果是往U盘拷贝文件，点取消就直接删除它！
                    copied_files = behavior_data.get('file_operation', {}).get('copied_files', [])
                    for cf in copied_files:
                        terminal_blocker.delete_file(cf)
                        print(f"   🗑️ 已强制删除U盘违规文件: {cf}")

                elif decision == 'report':
                    # 【上报管理员】—— 立即解除黑屏，管理员通过Web控制台独立审批
                    print(f"   📋 已上报管理员，解除本地黑屏。管理员将通过Web控制台处理该告警。")
                    terminal_blocker.stop_persistent_black_screen()
                    if target_file and os.path.exists(target_file):
                        terminal_blocker.restore_file_access(target_file)
                # ==============================================

            except Exception as e:
                print(f"⚠️ 决策上报失败：{e}")

            return result

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 上报成功 | 状态: {result.get('status')} | "
              f"操作: {result.get('action', 'pass')} | 信任分: {result.get('trust_score', 'N/A')}")
        action = result.get('action', 'pass')
        if action == 'block':
            print(f"\n🚨 收到阻断指令！执行本地阻断...")
            try:
                from blocker import terminal_blocker
                action_detail = behavior_data.get('action_detail', '')
                file_op = behavior_data.get('file_operation', {})

                # 【核心修改】提取被操作的文件路径
                target_file = None
                # 从窗口标题中提取文件路径（格式: APP:xxx | WINDOW:毕业设计系统 – C:\Users\...\xxx.py）
                if 'WINDOW:' in action_detail:
                    window_part = action_detail.split('WINDOW:')[1].strip()
                    # 尝试提取路径（Windows格式: 盘符:\... 或 macOS格式: /Users/...）
                    import re
                    path_match = re.search(r'([A-Za-z]:\\[^\s]+|/[^\s]+\.\w+)', window_part)
                    if path_match:
                        target_file = path_match.group(1)

                results = []

                # ============ 分级阻断策略 ============

                # ① 屏幕共享类：直接杀进程（腾讯会议/AnyDesk等不影响IDE）
                share_info = behavior_data.get('screen_share', {})
                if share_info.get('is_sharing') and share_info.get('app_name'):
                    share_app = share_info['app_name']
                    print(f"   检测到屏幕共享: {share_app}")
                    # 杀掉共享进程
                    share_process_map = {
                        'AnyDesk': 'AnyDesk.exe',
                        'TeamViewer': 'TeamViewer.exe',
                        '腾讯会议': 'wemeetapp.exe',
                        'Microsoft Teams': 'teams.exe',
                        'Zoom': 'zoom.exe',
                        '飞书': 'feishu.exe',
                        '钉钉': 'dingtalk.exe',
                        '向日葵': 'SunloginClient.exe',
                        'ToDesk': 'ToDesk.exe',
                    }
                    proc_name = share_process_map.get(share_app)
                    if proc_name:
                        r = terminal_blocker.kill_process_by_name(proc_name)
                        results.append(r)

                # ② 文件操作类：锁定文件权限，不杀IDE
                # ② 文件操作类：锁文件 + 关tab + 全屏遮罩
                if target_file and os.path.exists(target_file):
                    # 先锁文件权限
                    r = terminal_blocker.block_file_access(
                        target_file,
                        reason=file_op.get('operation_detail', '敏感文件操作')
                    )
                    results.append(r)
                    print(f"   已锁定文件: {target_file}")

                    # 立刻关闭当前编辑器标签页
                    terminal_blocker.close_current_editor_tab()

                    # 显示全屏阻断遮罩
                    terminal_blocker.show_blocking_overlay(
                        message="敏感文件操作已被阻断",
                        sub_message=f"文件: {os.path.basename(target_file)}\n该文件已被锁定，无法再次打开"
                    )

                # ③ USB操作：禁用USB端口
                if 'usb' in action_detail.lower() or 'u盘' in action_detail:
                    r = terminal_blocker.block_usb_devices()
                    results.append(r)

                # ④ 邮件外发：断开网络
                if '外发' in action_detail or 'email' in action_detail.lower():
                    r = terminal_blocker.block_network()
                    results.append(r)

                # ⑤ 如果没有匹配到任何具体类型，只锁文件不杀进程
                if not results and target_file:
                    pass  # 已经在②中处理
                elif not results:
                    # 最后兜底：不做破坏性操作，只记录
                    print(f"   ⚠️ 无法定位具体阻断目标，已记录告警但不执行破坏性操作")
                    results.append({'success': True, 'message': '已记录高危告警（未执行进程终止，保护IDE）'})

                for r in results:
                    if r.get('success'):
                        print(f"   ✅ {r['message']}")
                    else:
                        print(f"   ⚠️ {r['message']}")

            except Exception as e:
                print(f"   ⚠️ 阻断执行失败: {e}")
        return result
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 上报失败: {str(e)}")
        print(f"📦 数据已加入缓存队列，等待网络恢复后重试")
        upload_queue.add(behavior_data)
        return None


def run_collector(interval=10, server_url="http://127.0.0.1:5000/api/behavior/upload", user_id=1):
    print(f"\n{'=' * 60}")
    print(f"🚀 终端行为采集器已启动")
    print(f"👤 监视账号: 员工 ID {user_id}")
    print(f"📡 服务器地址: {server_url}")
    print(f"⏱️  上报间隔: {interval}秒")
    print(f"💻 设备 MAC: {get_device_unique_id()}")
    print(f"📦 断点续传: 已启用 (缓存文件: upload_cache.json)")
    print(f"✅ 6类核心行为采集: 已全部启用")
    if ENABLE_DIRECTORY_MONITOR:
        print(f"🔒 敏感目录监控: 已启用 (监控 {len(SENSITIVE_DIRECTORIES)} 个目录)")
        for i, dir_path in enumerate(SENSITIVE_DIRECTORIES, 1):
            print(f"   {i}. {dir_path}")
    print(f"{'=' * 60}\n")
    last_reported_action = None
    last_action_time = 0

    is_first_fetch = True  # 【新增】标记是否为第一次采集上报

    try:
        while True:
            behavior_data = collect_behavior()
            behavior_data['mock_user_id'] = user_id

            # ======== 【USB自动解黑】如果黑屏因U盘触发且U盘已拔出，自动关黑屏 ========
            from blocker import terminal_blocker
            if terminal_blocker.persistent_black_screen_active:
                file_op = behavior_data.get('file_operation', {})
                usb_still_present = file_op.get('has_usb_file_op') or file_op.get('has_usb_write')
                if not usb_still_present:
                    print(f"   ✅ USB设备已拔出，自动解除物理隔离黑屏。")
                    terminal_blocker.stop_persistent_black_screen()
                    last_reported_action = None
                    time.sleep(interval)
                    continue
            # ==============================================================

            # ======= 【核心修复 2】行为去重逻辑高危豁免 =======
            current_action = behavior_data.get('action_detail', '')
            file_op_status = behavior_data.get('file_operation', {})
            screen_share_status = behavior_data.get('screen_share', {})

            # 【关键】如果检测到 U盘插入、U盘写入、敏感文件操作、或屏幕共享，【绝对不能去重丢弃】，必须立刻上报！
            has_high_risk = (
                file_op_status.get('has_usb_file_op') or 
                file_op_status.get('has_usb_write') or 
                file_op_status.get('has_sensitive_file_op') or
                screen_share_status.get('is_sharing')  # 【新增】屏幕共享也属于高危行为
            )

            if not has_high_risk and current_action == last_reported_action and (time.time() - last_action_time) < 60:
                print(f"💤 [状态去重] 窗口无变化且无高危操作，跳过上报...")
                time.sleep(interval)
                continue

            last_reported_action = current_action
            last_action_time = time.time()
            # ============================================
            # ============================

            print(f"\n📊 采集数据:")
            print(f"   应用: {behavior_data['action_detail'].split('|')[0].replace('APP:', '').strip()}")
            print(f"   窗口: {behavior_data['action_detail'].split('|')[1].replace('WINDOW:', '').strip()}")
            print(f"   文件操作: {behavior_data['file_operation']['operation_detail']}")

            file_op = behavior_data['file_operation']
            if file_op.get('usb_mount_points'):
                print(f"   🚨 USB设备: {file_op['usb_mount_points']} | has_usb_file_op={file_op['has_usb_file_op']}")

            print(f"   邮件操作: {behavior_data['email_operation']['send_detail']}")
            print(f"   浏览器访问: {behavior_data['browser_operation']['active_tab_title']}")
            print(f"   CPU: {behavior_data['cpu_usage']}%")
            print(f"   类型: {behavior_data['behavior_type']}")

            result = send_behavior_to_server(behavior_data, server_url)

            # ======== 【新增】首次上报后醒目显示员工初始信任分 ========
            if is_first_fetch and result:
                init_score = result.get('trust_score', '未知')
                print(f"\n{'⭐' * 40}")
                print(f"✨ 成功连接服务器！员工 ID {user_id} 初始信任分: {init_score} 分")
                if isinstance(init_score, (int, float)):
                    if init_score < 60:
                        print(f"⚠️ 状态: [低信任] 敏感操作将受到严格限制！(且只有取消与上报按钮)")
                    elif init_score <= 80:
                        print(f"🛡️ 状态: [中信任] 敏感操作需触发二次确认。")
                    else:
                        print(f"✅ 状态: [高信任] 环境安全。")
                print(f"{'⭐' * 40}\n")
                is_first_fetch = False
            # ==========================================================

            if result is None and not upload_queue.is_uploading:
                print("\n🔄 触发队列处理（断点续传）...")
                upload_queue.process_queue(server_url)
            time.sleep(interval)
            if int(time.time()) % 60 == 0 and len(upload_queue.queue) > 0:
                status = upload_queue.get_queue_status()
                print(f"\n📦 队列状态: {status['queue_size']} 条待上传 | 上传中: {status['is_uploading']}")
                if not status['is_uploading']:
                    upload_queue.process_queue(server_url)
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断，采集器已停止")
        print("\n💾 保存缓存数据...")
        upload_queue._save_cache()
        status = upload_queue.get_queue_status()
        print(f"✅ 已保存 {status['queue_size']} 条数据到 {status['cache_file']}")
        print(f"👋 下次启动时将继续上传这些数据（断点续传）")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='企业安全客户端 Agent')
    parser.add_argument('--user', type=int, default=1, help='要监视的员工 ID (例如: --user 20)')
    parser.add_argument('--interval', type=int, default=10, help='数据采集上报间隔 (秒)')
    args = parser.parse_args()

    run_collector(interval=args.interval, user_id=args.user)
