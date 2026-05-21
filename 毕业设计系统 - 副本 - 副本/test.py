import wmi
c = wmi.WMI()
for disk in c.Win32_LogicalDisk(DriveType=2):
    print(f"发现可移动磁盘: {disk.DeviceID}")
