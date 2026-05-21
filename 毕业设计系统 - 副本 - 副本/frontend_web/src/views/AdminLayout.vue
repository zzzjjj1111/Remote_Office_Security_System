<template>
  <el-container class="admin-layout">
    <el-aside width="240px" class="aside">
      <div class="logo-box">
        <el-icon style="font-size: 24px;"><Monitor /></el-icon>
        <span style="font-size: 20px; margin-left: 8px; font-weight: 800;">基于行为基线防护系统</span>
      </div>
      <el-menu active-text-color="#409EFF" background-color="#2c3e50" :default-active="$route.path" router>
        <el-menu-item index="/admin/dashboard" class="uiverse-menu-item">
          <el-icon><DataLine /></el-icon> <span>安全总览</span>
        </el-menu-item>
        <el-menu-item index="/admin/baseline" class="uiverse-menu-item">
          <el-icon><TrendCharts /></el-icon> <span>行为基线</span>
        </el-menu-item>
        <el-menu-item index="/admin/settings" class="uiverse-menu-item">
          <el-icon><Setting /></el-icon> <span>规则配置</span>
        </el-menu-item>
        <el-menu-item index="/admin/alerts" class="uiverse-menu-item">
          <el-icon><Bell /></el-icon> <span>异常告警</span>
        </el-menu-item>
        <el-menu-item index="/admin/logs" class="uiverse-menu-item">
          <el-icon><Document /></el-icon> <span>日志审计</span>
        </el-menu-item>
        <el-menu-item index="/admin/devices" class="uiverse-menu-item">
          <el-icon><Monitor /></el-icon> <span>终端管理</span>
        </el-menu-item>

        <el-divider style="border-color: #555; margin: 10px 0;" />

        <el-menu-item @click="$router.push('/portal/oa')" class="uiverse-menu-item">
          <el-icon><User /></el-icon> <span>切换员工门户</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container style="z-index: 1;">
      <el-header class="admin-header">
        <div class="header-left">
          <span>当前身份：安全管理员 (Super Admin)</span>
        </div>
        <div class="header-right">
          <el-button type="danger" size="small" @click="logout">安全登出</el-button>
        </div>
      </el-header>

      <el-main class="admin-main">
        <router-view></router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { Monitor, DataLine, Bell, Setting, Document, TrendCharts, User } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const logout = () => {
  localStorage.removeItem('sys_token')
  router.push('/login')
}
</script>

<style scoped>
.admin-layout {
  height: 100vh;
  width: 100vw;
  background: linear-gradient(45deg, #3498db, #2ecc71);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
  position: relative;
  overflow: hidden;
}

.admin-layout::before {
  content: "";
  position: absolute;
  width: 100%;
  height: 100%;
  top: 0;
  left: 0;
  background-image: linear-gradient(
      90deg,
      rgba(255, 255, 255, 0.1) 1px,
      transparent 1px
    ),
    linear-gradient(rgba(255, 255, 255, 0.1) 1px, transparent 1px);
  background-size: 20px 20px;
  pointer-events: none;
  z-index: 0;
}

.aside {
  background: linear-gradient(to bottom, #f4c4ec, #08f6cc, #24243e) !important;
  display: flex;
  flex-direction: column;
  z-index: 2;
  box-shadow: 2px 0 8px rgb(132, 253, 232);
}
.logo-box {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #101010;
  font-size: 16px;
  font-weight: bold;
  gap: 8px;
  border-bottom: 1px solid rgba(14, 14, 14, 0.2);
  background-color: transparent;
}
.el-menu {
  border-right: none;
  background-color: transparent !important;
}
.admin-header {
  background-color: rgb(150, 248, 205);
  backdrop-filter: blur(5px);
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 2;
}
/* 新增：当前身份文字样式（加粗+黑色） */
.header-left span {
  font-weight: 700;
  color: #000000;
  font-size: 20px;
}
.admin-main {
  padding: 24px;
  height: calc(100vh - 60px);
  overflow-y: auto;
  position: relative;
  z-index: 1;
}
</style>
<style>
/* Override element plus menu background inside aside */
.admin-layout .el-menu-item {
  background-color: transparent !important;
}
.admin-layout .el-menu-item.is-active {
  background-color: rgba(64,158,255,0.2) !important;
  border-radius: 16px;
}

/* Uiverse.io Sidebar animation styling */
.admin-layout .uiverse-menu-item {
  display: flex !important;
  align-items: center !important;
  font-family: inherit;
  cursor: pointer;
  font-weight: 700;
  font-size: 17px;
  color: #000 !important;
  background: transparent !important;
  border: none;
  letter-spacing: 0.05em;
  border-radius: 16px !important;
  margin: 4px 8px !important;
  width: calc(100% - 16px) !important;
  transition: all 0.3s ease;
}

.admin-layout .uiverse-menu-item .el-icon {
  margin-right: 3px;
  transition: transform 0.5s cubic-bezier(0.76, 0, 0.24, 1);
}

.admin-layout .uiverse-menu-item span {
  transition: transform 0.5s cubic-bezier(0.76, 0, 0.24, 1);
}

/* Base element-plus hover logic override */
.admin-layout .el-menu-item:hover {
  background-color: rgba(255,255,255,0.3) !important;
}

.admin-layout .uiverse-menu-item:hover .el-icon {
  transform: translateX(5px) rotate(90deg);
}

.admin-layout .uiverse-menu-item:hover span {
  transform: translateX(7px);
}
</style>