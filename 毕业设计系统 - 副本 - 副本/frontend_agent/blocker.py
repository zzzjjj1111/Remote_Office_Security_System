"""
终端阻断执行模块
接收后端的block指令，在本地执行阻断操作
支持：杀进程、断USB、网络隔离、二次确认弹窗
"""

import platform
import subprocess
import time
import threading
import os


class TerminalBlocker:
    """
    终端阻断执行器
    跨平台支持 Windows/macOS
    """
    
    def __init__(self):
        self.system = platform.system()
        self.blocked_processes = []  # 被阻断的进程列表
        self.is_network_blocked = False  # 网络是否被阻断
        # 👇 【新增】用于高频黑屏守护的变量
        self.persistent_black_screen_active = False
        self.forbidden_window_title = None
        self.black_overlay_root = None
    
    def kill_process_by_name(self, process_name):
        """
        根据进程名杀死进程
        
        Args:
            process_name: 进程名（如 'chrome.exe', 'WeChat.exe'）
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'killed_count': int
            }
        """
        try:
            if self.system == "Windows":
                # Windows: 使用taskkill
                result = subprocess.run(
                    ['taskkill', '/F', '/IM', process_name],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    killed_count = result.stdout.count('成功')
                    self.blocked_processes.append({
                        'name': process_name,
                        'killed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'count': killed_count
                    })
                    return {
                        'success': True,
                        'message': f'已终止 {killed_count} 个 {process_name} 进程',
                        'killed_count': killed_count
                    }
                else:
                    return {
                        'success': False,
                        'message': f'终止进程失败: {result.stderr}',
                        'killed_count': 0
                    }
            
            elif self.system == "Darwin":  # macOS
                # macOS: 使用pkill
                result = subprocess.run(
                    ['pkill', '-f', process_name],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    self.blocked_processes.append({
                        'name': process_name,
                        'killed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'count': 1
                    })
                    return {
                        'success': True,
                        'message': f'已终止 {process_name} 进程',
                        'killed_count': 1
                    }
                else:
                    return {
                        'success': False,
                        'message': f'终止进程失败: {result.stderr}',
                        'killed_count': 0
                    }
            
            return {
                'success': False,
                'message': f'不支持的操作系统: {self.system}',
                'killed_count': 0
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'执行异常: {str(e)}',
                'killed_count': 0
            }
    
    def block_usb_devices(self):
        """
        禁用USB存储设备
        
        Returns:
            dict: 执行结果
        """
        try:
            if self.system == "Windows":
                # Windows: 禁用USB存储（通过注册表）
                print("\n🔒 【真实执行】Windows USB存储禁用")
                print("   执行命令: reg add HKLM\\SYSTEM\\CurrentControlSet\\Services\\USBSTOR /v Start /t REG_DWORD /d 4 /f")
                
                # 真实执行（需要管理员权限）
                result = subprocess.run(
                    ['reg', 'add', 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\USBSTOR', 
                     '/v', 'Start', '/t', 'REG_DWORD', '/d', '4', '/f'], 
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("   ✅ USB存储设备已禁用（需重启生效）")
                    return {
                        'success': True,
                        'message': 'USB存储设备已禁用（需重启生效）'
                    }
                else:
                    print(f"   ⚠️ 执行失败: {result.stderr}")
                    return {
                        'success': False,
                        'message': f'USB禁用失败（可能需要管理员权限）: {result.stderr}'
                    }
            
            elif self.system == "Darwin":
                # macOS: 禁用USB存储
                print("\n🔒 【真实执行】macOS USB存储禁用")
                print("   执行命令: sudo kextunload -b com.apple.driver.AppleUSBMassStorageClassDriver")
                
                result = subprocess.run(
                    ['sudo', 'kextunload', '-b', 'com.apple.driver.AppleUSBMassStorageClassDriver'],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("   ✅ USB存储设备已禁用")
                    return {
                        'success': True,
                        'message': 'USB存储设备已禁用（需sudo权限）'
                    }
                else:
                    print(f"   ⚠️ 执行失败: {result.stderr}")
                    return {
                        'success': False,
                        'message': f'USB禁用失败（需要sudo权限）: {result.stderr}'
                    }
            
            return {
                'success': False,
                'message': f'不支持的操作系统: {self.system}'
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'执行异常: {str(e)}'
            }
    
    def restore_usb_devices(self):
        """
        恢复USB存储设备
        
        Returns:
            dict: 执行结果
        """
        try:
            if self.system == "Windows":
                print("\n🔓 【真实执行】Windows USB存储恢复")
                print("   执行命令: reg add HKLM\\SYSTEM\\CurrentControlSet\\Services\\USBSTOR /v Start /t REG_DWORD /d 3 /f")
                
                result = subprocess.run(
                    ['reg', 'add', 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\USBSTOR', 
                     '/v', 'Start', '/t', 'REG_DWORD', '/d', '3', '/f'], 
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("   ✅ USB存储设备已恢复")
                    return {
                        'success': True,
                        'message': 'USB存储设备已恢复'
                    }
                else:
                    print(f"   ⚠️ 执行失败: {result.stderr}")
                    return {
                        'success': False,
                        'message': f'USB恢复失败: {result.stderr}'
                    }
            
            elif self.system == "Darwin":
                print("\n🔓 【真实执行】macOS USB存储恢复")
                print("   执行命令: sudo kextload -b com.apple.driver.AppleUSBMassStorageClassDriver")
                
                result = subprocess.run(
                    ['sudo', 'kextload', '-b', 'com.apple.driver.AppleUSBMassStorageClassDriver'],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("   ✅ USB存储设备已恢复")
                    return {
                        'success': True,
                        'message': 'USB存储设备已恢复'
                    }
                else:
                    print(f"   ⚠️ 执行失败: {result.stderr}")
                    return {
                        'success': False,
                        'message': f'USB恢复失败: {result.stderr}'
                    }
            
            return {
                'success': False,
                'message': f'不支持的操作系统: {self.system}'
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'执行异常: {str(e)}'
            }
    
    def block_network(self):
        """
        断开网络连接（隔离终端）
        
        Returns:
            dict: 执行结果
        """
        try:
            if self.system == "Windows":
                # Windows: 禁用所有网络适配器
                print("\n🚫 【真实执行】Windows 网络隔离")
                print("   执行命令: netsh interface set interface \"以太网\" disabled")
                
                # 尝试禁用以太网
                result = subprocess.run(
                    ['netsh', 'interface', 'set', 'interface', '以太网', 'disabled'],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("   ✅ 以太网已禁用（终端隔离）")
                    self.is_network_blocked = True
                    return {
                        'success': True,
                        'message': '网络已断开（终端隔离）'
                    }
                else:
                    # 尝试禁用Wi-Fi
                    print(f"   ⚠️ 以太网禁用失败，尝试禁用Wi-Fi...")
                    result_wifi = subprocess.run(
                        ['netsh', 'interface', 'set', 'interface', 'Wi-Fi', 'disabled'],
                        capture_output=True,
                        text=True
                    )
                    
                    if result_wifi.returncode == 0:
                        print("   ✅ Wi-Fi已禁用（终端隔离）")
                        self.is_network_blocked = True
                        return {
                            'success': True,
                            'message': 'Wi-Fi已断开（终端隔离）'
                        }
                    else:
                        print(f"   ⚠️ 网络禁用失败: {result.stderr}")
                        return {
                            'success': False,
                            'message': f'网络隔离失败（可能需要管理员权限）'
                        }
            
            elif self.system == "Darwin":
                # macOS: 关闭所有网络接口
                print("\n🚫 【真实执行】macOS 网络隔离")
                print("   执行命令: sudo ifconfig en0 down")
                
                result = subprocess.run(
                    ['sudo', 'ifconfig', 'en0', 'down'],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("   ✅ 网络接口已禁用（终端隔离）")
                    self.is_network_blocked = True
                    return {
                        'success': True,
                        'message': '网络已断开（终端隔离）'
                    }
                else:
                    print(f"   ⚠️ 执行失败: {result.stderr}")
                    return {
                        'success': False,
                        'message': f'网络隔离失败（需要sudo权限）: {result.stderr}'
                    }
            
            return {
                'success': False,
                'message': f'不支持的操作系统: {self.system}'
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'执行异常: {str(e)}'
            }
    
    def restore_network(self):
        """
        恢复网络连接
        
        Returns:
            dict: 执行结果
        """
        try:
            if self.system == "Windows":
                print("\n✅ 【真实执行】Windows 网络恢复")
                print("   执行命令: netsh interface set interface \"以太网\" enabled")
                
                result = subprocess.run(
                    ['netsh', 'interface', 'set', 'interface', '以太网', 'enabled'],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("   ✅ 以太网已恢复")
                    self.is_network_blocked = False
                    return {
                        'success': True,
                        'message': '网络已恢复'
                    }
                else:
                    # 尝试恢复Wi-Fi
                    result_wifi = subprocess.run(
                        ['netsh', 'interface', 'set', 'interface', 'Wi-Fi', 'enabled'],
                        capture_output=True,
                        text=True
                    )
                    
                    if result_wifi.returncode == 0:
                        print("   ✅ Wi-Fi已恢复")
                        self.is_network_blocked = False
                        return {
                            'success': True,
                            'message': 'Wi-Fi已恢复'
                        }
                    else:
                        print(f"   ⚠️ 网络恢复失败")
                        return {
                            'success': False,
                            'message': '网络恢复失败'
                        }
            
            elif self.system == "Darwin":
                print("\n✅ 【真实执行】macOS 网络恢复")
                print("   执行命令: sudo ifconfig en0 up")
                
                result = subprocess.run(
                    ['sudo', 'ifconfig', 'en0', 'up'],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    print("   ✅ 网络接口已恢复")
                    self.is_network_blocked = False
                    return {
                        'success': True,
                        'message': '网络已恢复'
                    }
                else:
                    print(f"   ⚠️ 执行失败: {result.stderr}")
                    return {
                        'success': False,
                        'message': f'网络恢复失败: {result.stderr}'
                    }
            
            return {
                'success': False,
                'message': f'不支持的操作系统: {self.system}'
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'执行异常: {str(e)}'
            }
    
    def execute_block_action(self, action_detail, block_type='full'):
        """
        执行阻断动作
        
        Args:
            action_detail: 行为详情（用于判断阻断类型）
            block_type: 阻断类型
                - 'process': 仅杀进程
                - 'usb': 禁用USB
                - 'network': 断网
                - 'full': 全面阻断（杀进程+USB+网络）
        
        Returns:
            list: 执行结果列表
        """
        results = []
        
        print(f"\n{'='*60}")
        print(f"🚨 【终端阻断执行】")
        print(f"{'='*60}")
        print(f"触发行为: {action_detail}")
        print(f"阻断类型: {block_type}")
        print(f"{'='*60}")
        
        # 1. 杀进程（如果是敏感进程）
        if block_type in ['process', 'full']:
            # 检测常见敏感进程
            sensitive_processes = ['AnyDesk.exe', 'TeamViewer.exe', 'chrome.exe', 'firefox.exe']
            
            for proc in sensitive_processes:
                if proc.lower() in action_detail.lower():
                    print(f"\n 检测到敏感进程: {proc}")
                    result = self.kill_process_by_name(proc)
                    results.append(result)
                    print(f"   结果: {result['message']}")
        
        # 2. 禁用USB（如果是USB相关行为）
        if block_type in ['usb', 'full']:
            if 'usb' in action_detail.lower() or 'u盘' in action_detail:
                print("\n 检测到USB操作")
                result = self.block_usb_devices()
                results.append(result)
                print(f"   结果: {result['message']}")
        
        # 3. 断开网络（高风险操作）
        if block_type == 'network' or (block_type == 'full' and '外发' in action_detail):
            print("\n🎯 高风险操作，执行网络隔离")
            result = self.block_network()
            results.append(result)
            print(f"   结果: {result['message']}")
        
        print(f"\n{'='*60}")
        print(f"✅ 阻断执行完成，共执行 {len(results)} 项操作")
        print(f"{'='*60}\n")
        
        return results

    def delete_file(self, file_path):
        """
        【新增】强制删除违规拷贝到U盘的文件，防数据泄露
        """
        try:
            file_path = os.path.abspath(file_path)
            if os.path.exists(file_path):
                # 解除可能存在的文件占用或只读属性 (Windows)
                if self.system == "Windows":
                    subprocess.run(f'attrib -r -s -h "{file_path}"', shell=True, capture_output=True)
                os.remove(file_path)
                return {'success': True, 'message': f'已拦截并强制删除U盘文件: {os.path.basename(file_path)}'}
            return {'success': False, 'message': '文件不存在，可能已被提前移除'}
        except Exception as e:
            return {'success': False, 'message': f'删除U盘文件失败: {str(e)}'}

    def block_file_access(self, file_path, reason="敏感文件操作"):
        """
        阻断对指定文件的访问（不杀IDE，只锁文件）

        原理：通过 Windows icacls / macOS chmod 撤销当前用户对文件的读取权限
        效果：文件内容已经在IDE中打开的不受影响（用户态无法撤回），
              但保存、另存、再次打开均被系统拒绝

        Args:
            file_path: 要阻断的文件路径
            reason: 阻断原因

        Returns:
            dict: 执行结果
        """
        try:
            print(f"\n{'=' * 60}")
            print(f"🔒 【文件级阻断】")
            print(f"   文件: {file_path}")
            print(f"   原因: {reason}")
            print(f"{'=' * 60}")

            # 规范化路径
            file_path = os.path.abspath(file_path)

            if not os.path.exists(file_path):
                return {
                    'success': False,
                    'message': f'文件不存在: {file_path}'
                }

            if self.system == "Windows":
                # Windows: 使用 icacls 拒绝当前用户的读取权限
                username = os.environ.get('USERNAME', os.environ.get('USER', 'Everyone'))
                # /deny 会拒绝该用户的读取权限
                cmd = f'icacls "{file_path}" /deny {username}:(R)'
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

                if result.returncode == 0:
                    return {
                        'success': True,
                        'message': f'已阻断文件访问: {os.path.basename(file_path)}（用户 {username} 再无读取权限）'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'icacls 失败: {result.stderr}'
                    }

            elif self.system == "Darwin":
                # macOS: 使用 chmod 移除所有者的读权限
                cmd = f'chmod u-r "{file_path}"'
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

                if result.returncode == 0:
                    return {
                        'success': True,
                        'message': f'已阻断文件访问: {os.path.basename(file_path)}'
                    }
                else:
                    return {
                        'success': False,
                        'message': f'chmod 失败: {result.stderr}'
                    }

            return {
                'success': False,
                'message': f'不支持的操作系统: {self.system}'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'文件阻断异常: {str(e)}'
            }

    def restore_file_access(self, file_path):
        """
        恢复文件访问权限（管理员审批通过后使用）

        Args:
            file_path: 要恢复的文件路径
        """
        try:
            file_path = os.path.abspath(file_path)
            if not os.path.exists(file_path):
                return {'success': False, 'message': '文件不存在'}

            if self.system == "Windows":
                username = os.environ.get('USERNAME', os.environ.get('USER', 'Everyone'))
                # /grant 会恢复该用户的读取权限
                cmd = f'icacls "{file_path}" /grant {username}:(R) /remove:d {username}'
                subprocess.run(cmd, capture_output=True, text=True, shell=True)
            elif self.system == "Darwin":
                cmd = f'chmod u+r "{file_path}"'
                subprocess.run(cmd, capture_output=True, text=True, shell=True)

            return {'success': True, 'message': f'已恢复: {os.path.basename(file_path)}'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def get_block_status(self):
        """
        获取当前阻断状态
        
        Returns:
            dict: 阻断状态
        """
        return {
            'network_blocked': self.is_network_blocked,
            'blocked_processes': self.blocked_processes,
            'block_count': len(self.blocked_processes)
        }
    
    def show_confirmation_dialog(self, file_name, operation_type, sensitive_words, trust_score=100, trigger_reason='anomaly_behavior'):

        """
        显示二次确认弹窗
        
        Args:
            file_name: 文件名
            operation_type: 操作类型
            sensitive_words: 命中的敏感词列表
            trust_score: 员工当前信任分（用于动态渲染按钮）
        
        Returns:
            str: 'allow'(确认继续) / 'block'(取消操作) / 'report'(上报管理员)
        """
        try:
            import tkinter as tk
            from tkinter import messagebox, simpledialog
            
            result = {'decision': 'block'}  # 默认取消
            
            def show_dialog():
                # 创建主窗口
                root = tk.Tk()
                root.title("🔒 终端安全防护")
                root.geometry("450x300")
                root.resizable(False, False)
                root.attributes('-topmost', True)  # 置顶
                
                # 居中显示
                root.update_idletasks()
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                x = (screen_width - 450) // 2
                y = (screen_height - 300) // 2
                root.geometry(f"450x300+{x}+{y}")
                
                # 标题
                title_label = tk.Label(root, text="⚠️ 安全提醒", font=("微软雅黑", 14, "bold"), fg="#ff4d4f")
                title_label.pack(pady=(20, 10))
                
                # 内容区域
                content_frame = tk.Frame(root)
                content_frame.pack(padx=20, pady=10, fill=tk.X)
                
                # 文件信息
                # 【修复】根据实际触发原因显示精准提示文字
                trigger_texts = {
                    'sensitive_words': '检测到敏感内容操作：',
                    'usb_write': '检测到U盘文件写入：',
                    'usb_device': '检测到外接存储设备：',
                    'low_trust': '信任分过低，操作需确认：',
                    'anomaly_behavior': '检测到异常行为偏离：'
                }
                trigger_title = trigger_texts.get(trigger_reason, '检测到高风险行为：')
                tk.Label(content_frame, text=trigger_title, font=("微软雅黑", 10, "bold"), anchor="w").pack(anchor="w",
                                                                                                            pady=(0, 5))
                # 【修复】USB 场景下不显示误导的"文件"信息
                if trigger_reason in ('usb_device', 'usb_write'):
                    tk.Label(content_frame, text=f"💾 U盘设备已接入，信任分过低触发二次确认",
                             font=("微软雅黑", 9), fg="#e6a23c", anchor="w").pack(anchor="w", pady=2)
                elif trigger_reason == 'low_trust':
                    tk.Label(content_frame, text=f"📄 当前窗口：{file_name}", font=("微软雅黑", 9), fg="#666",
                             anchor="w").pack(anchor="w", pady=2)
                else:
                    tk.Label(content_frame, text=f"📄 文件：{file_name}", font=("微软雅黑", 9), fg="#666",
                             anchor="w").pack(anchor="w", pady=2)
                tk.Label(content_frame, text=f"🔧 操作：{operation_type}", font=("微软雅黑", 9), fg="#666",
                         anchor="w").pack(anchor="w", pady=2)

                if sensitive_words:
                    tk.Label(content_frame, text=f"🔑 命中敏感词：{', '.join(sensitive_words)}", font=("微软雅黑", 9), fg="#ff4d4f", anchor="w").pack(anchor="w", pady=2)

                tk.Frame(content_frame, height=1, bg="#e8e8e8").pack(fill=tk.X, pady=10)
                
                tk.Label(content_frame, text="请确认是否为工作需要？", font=("微软雅黑", 10), fg="#333").pack(anchor="w", pady=(0, 10))

                button_frame = tk.Frame(root)
                button_frame.pack(pady=(10, 20), fill=tk.X, padx=20)
                
                def on_confirm():
                    result['decision'] = 'allow'
                    root.destroy()
                
                def on_cancel():
                    result['decision'] = 'block'
                    root.destroy()
                
                def on_report():
                    result['decision'] = 'report'
                    root.destroy()
                
                # 动态按钮组
                # 【核心修改】如果信任分>=60（中信任），才渲染"确认"按钮；低信任则直接隐藏该按钮！
                if trust_score >= 60:
                    btn_confirm = tk.Button(button_frame, text="✓ 确认继续", command=on_confirm,
                                            bg="#52c41a", fg="white", font=("微软雅黑", 10, "bold"),
                                            width=12, relief=tk.RAISED, cursor="hand2")
                    btn_confirm.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
                
                btn_cancel = tk.Button(button_frame, text="✗ 取消操作", command=on_cancel,
                                       bg="#ff4d4f", fg="white", font=("微软雅黑", 10, "bold"),
                                       width=12, relief=tk.RAISED, cursor="hand2")
                btn_cancel.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
                                
                btn_report = tk.Button(button_frame, text="📋 上报管理员", command=on_report,
                                      bg="#faad14", fg="white", font=("微软雅黑", 10, "bold"),
                                      width=12, relief=tk.RAISED, cursor="hand2")
                btn_report.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
                
                # 关闭按钮处理
                def on_closing():
                    result['decision'] = 'block'  # 关闭窗口默认取消
                    root.destroy()
                
                root.protocol("WM_DELETE_WINDOW", on_closing)
                
                # 运行主循环
                root.mainloop()
            
            # 在主线程中显示（tkinter要求）
            dialog_thread = threading.Thread(target=show_dialog)
            dialog_thread.start()
            dialog_thread.join()  # 等待用户选择
            
            print(f"📋 用户决策：{result['decision']}")
            return result['decision']
            
        except Exception as e:
            print(f"⚠️ 弹窗显示失败：{e}")
            return 'block'  # 失败时默认阻断

    def close_current_editor_tab(self):
        """
        关闭当前IDE/编辑器的标签页（不杀进程）
        配合 icacls 锁文件后，用户再也打不开
        
        【重要说明】
        - PyCharm/VSCode 的多个 tab 不是子进程，都在同一个主进程中
        - 不能用 kill 命令关闭单个 tab（会杀掉整个 IDE）
        - 只能通过快捷键关闭标签页
        """
        try:
            if self.system == "Windows":
                import win32gui
                import win32com.client

                hwnd = win32gui.GetForegroundWindow()
                window_title = win32gui.GetWindowText(hwnd)

                # 只对 IDE 窗口操作（安全保护：不会误关其他应用）
                ide_indicators = ['pycharm', 'idea', 'vscode', 'visual studio', 'code', 'notepad', '记事本']
                if not any(indicator in window_title.lower() for indicator in ide_indicators):
                    return {'success': False, 'message': '前台窗口不是编辑器，跳过'}

                shell = win32com.client.Dispatch("WScript.Shell")
                
                # 【增强】多重快捷键确保关闭标签页
                # 1. Ctrl+W - 关闭当前标签页（通用）
                print(f"   📑 正在关闭标签页: {window_title[:60]}")
                shell.SendKeys('^w')
                time.sleep(0.2)
                
                # 2. Ctrl+F4 - 另一种关闭标签页方式（更可靠）
                shell.SendKeys('^{F4}')
                time.sleep(0.2)
                
                # 3. Esc - 关闭可能的对话框
                shell.SendKeys('{ESC}')
                time.sleep(0.2)

                print(f"   ✅ 已发送关闭标签页快捷键")
                return {'success': True, 'message': '已关闭敏感文件标签页（文件权限已锁定）'}

            elif self.system == "Darwin":
                # macOS: 发送 Cmd+W
                script = 'tell application "System Events" to keystroke "w" using command down'
                subprocess.run(['osascript', '-e', script], capture_output=True)
                time.sleep(0.2)
                # 再发送一次确保关闭
                subprocess.run(['osascript', '-e', script], capture_output=True)
                return {'success': True, 'message': '已关闭当前编辑标签页'}

            return {'success': False, 'message': '不支持的操作系统'}

        except Exception as e:
            return {'success': False, 'message': f'关闭标签页失败: {str(e)}'}

    def start_persistent_black_screen(self, forbidden_title, trigger_reason='anomaly_behavior'):

        """【新增】启动高频守护黑屏线程"""
        if self.persistent_black_screen_active:
            return

        self.persistent_black_screen_active = True
        self.forbidden_window_title = forbidden_title
        print(f"   🛡️ 已启动高频黑屏守护，目标窗口: {forbidden_title[:20]}...")

        def _monitor_and_block():
            import tkinter as tk
            import win32gui

            # 创建黑屏窗口但不立即显示
            root = tk.Tk()
            root.title("安全物理隔离")
            root.attributes('-fullscreen', True)
            root.attributes('-topmost', True)
            root.configure(bg='black')
            root.withdraw()  # 先隐藏

            black_screen_texts = {
                'sensitive_words': ('🛑 高风险敏感内容！','系统检测到敏感关键词，已进行物理遮蔽隔离\n请立即停止当前操作！'),
                'usb_write': ('🛑 未授权U盘写入！','检测到向U盘写入文件行为，系统已进行物理遮蔽隔离\n请立即停止并拔除U盘！'),
                'usb_device': ('🛑 未授权外接设备！','检测到未授权U盘设备接入，系统已进行物理遮蔽隔离\n请立即拔除外接存储设备！'),
                'low_trust': ('🛑 信任分不足！', '您的信任分过低，此操作需额外确认\n请联系管理员或等待信任分恢复'),
                'anomaly_behavior': ('🛑 异常行为告警！','系统检测到行为模式偏离正常基线\n已进行物理遮蔽隔离，请确认操作合法性')
            }
            black_title, black_subtitle = black_screen_texts.get(
                trigger_reason,
                ('🛑 安全风险告警！', '系统检测到安全风险，已进行物理遮蔽隔离\n请在弹窗中确认或取消操作')
            )
            tk.Label(root, text=black_title, font=('Microsoft YaHei', 40, 'bold'), bg='black', fg='red').pack(pady=(200, 20))
            tk.Label(root, text=black_subtitle,
                     font=('Microsoft YaHei', 20), bg='black', fg='white').pack()

            # 禁用关闭
            root.protocol("WM_DELETE_WINDOW", lambda: None)

            while self.persistent_black_screen_active:
                # 高频检测（0.2秒一次）
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    current_title = win32gui.GetWindowText(hwnd)
                    # 如果当前窗口包含敏感文件名，瞬间显示黑屏！
                    if self.forbidden_window_title in current_title:
                        if root.state() != 'normal':
                            root.deiconify()  # 显示并置顶
                            root.attributes('-topmost', True)
                    else:
                        if root.state() == 'normal':
                            root.withdraw()  # 切到其他窗口就隐藏

                root.update()
                time.sleep(0.2)

            root.destroy()

        # 启动守护线程
        t = threading.Thread(target=_monitor_and_block, daemon=True)
        t.start()

    def stop_persistent_black_screen(self):
        """【新增】停止高频黑屏守护"""
        self.persistent_black_screen_active = False

    def show_blocking_overlay(self, message="操作已被系统阻断", sub_message=""):
        """原有的一次性阻断提示框（保留作为警告用）"""
        pass  # 这里为了不卡死主线程，可以配合上面的守护线程使用。在新的设计中，我们主要依赖上面的物理隔离。

# 全局阻断器实例
terminal_blocker = TerminalBlocker()
