#  零信任安全管理引擎 - 本地部署指南

本项目采用 **前后端分离** 架构，主要由三部分组成：
1. **Frontend Web** (Vue 3 + Vite + Element Plus)：安全管理控制台前端
2. **Backend** (Python Flask)：核心 API 与鉴权、状态管理后端
3. **Client Agent** (Python 脚本)：模拟终端安全探针（上报行为与信任分变更）

为了在本地环境正常启动项目，请按照以下步骤配置依赖并运行。

---

##  一、 环境前置要求

在运行本项目前，请确保此电脑已安装以下基础环境：
- **Node.js**: (推荐 v16 或 v18+) [点击下载](https://nodejs.org/)
- **Python**: (推荐 Python 3.8 到 3.10+) [点击下载](https://www.python.org/downloads/)
- **Vscode** (或其他代码编辑器) - 推荐安装 \Vue - Official\ 和 \Python\ 插件
- **数据库**: 本项目使用本机的 MySQL (请确保已安装并在 3306 端口启动 mysql, default密码假设为 \123456\)

---

##  二、 数据库初始化与海量数据导入 (Database & Mock Data)

为了在答辩演示时达到企业级态势感知的震撼效果，本项目配有万级量级的数据生成引擎。

### 1. 初始化数据库与导入海量演示数据
首次运行需要进行配置，这会自动在你的 MySQL 中建库（或者清空旧表）并插入大量真实人员架构、设备漏洞、异常行为和拦截动作模型。
如果你在根目录下，新开一个终端：
\\\ash
cd database
python insert_directly.py
\\\
*(提示成功 \Massive dataset successfully inserted... \ 后，你的数据库将会拥有 1万+ 条终端探针日志与告警记录，大屏展示效果满级拉满。)*

---

##  三、 后端环境配置与启动 (Backend)

后端采用轻量级的 Python Flask 框架，连接上述已初始化的 MySQL。

### 1. 进入后端目录
打开终端，进入到后端文件夹：
\\\ash
cd backend
\\\

### 2. 安装依赖库
在激活的虚拟环境或者系统 Python 中执行：
\\\ash
pip install flask flask-cors sqlalchemy flask-sqlalchemy pymysql pydantic requests
\\\

### 3. 启动后端服务
\\\ash
python app.py
\\\
控制台会显示类似 \Running on http://127.0.0.1:5000\。**请保持该终端窗口不要关闭**。

---

##  四、 前端环境配置与运行 (Frontend Web)

前端是一个 Vite 驱动的 Vue3 工程，集成了 Echarts 态势图与 Uiverse.io 高级动效。

### 1. 新开一个终端，进入前端目录
\\\ash
cd frontend_web
npm run dev
\\\

### 2. 安装 Node.js 依赖
执行配置好的 \package.json\ 中的库包下载：
\\\ash
npm install
\\\
*(如果网络较慢，建议更换镜像源：\
pm config set registry https://registry.npmmirror.com\ 后再执行安装)*

### 3. 启动本地开发服务器
\\\ash
npm run dev
\\\
如果你看到成功启动（如 \http://localhost:5173/\），打开浏览器访问即可！

---

##  五、 (可选) 运行终端探针脚本 (Client Agent)

如果你需要演示实时产生的**非法访问、终端行为（会导致态势大屏的信任分实景下降）**，可以独立运行前端探针：

1. 在项目**根目录**下，新开专门的终端。
2. 运行 Python 客户端脚本：
\\\ash
cd frontend_agent
python client_agent.py
\\\
此脚本会定期向后端发包，使页面信任分发生更真实的高频抖动。
cd E:\毕业设计\毕业设计系统\frontend_agent
python collector.py --user 18 --interval 5
---

##  常见问题与排错 (FAQ)

1. **问：前端点击登录提示 "网络连接或验证失败"？**
   答：通常是因为**后端(Python Flask) 没启动**或者由于安全设置阻止了 5000 端口。请首先检查数据库密码是否对应。

2. **问：大屏 (Dashboard) 的统计图表加载不出来？**
   答：确认后端已启动，并确保前置的步骤中跑通了 \insert_directly.py\，保证图表有庞大数据源作为渲染基础。

3. **默认账号：**
   大批量注入后的环境默认内置了以下可用账号作为管理员：
   **账号：\dmin\**，密码任意输入（如 \123456\）即可。
