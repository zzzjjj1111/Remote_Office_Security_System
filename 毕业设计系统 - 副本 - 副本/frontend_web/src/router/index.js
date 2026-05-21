// ========== 所有import统一放在最顶部 ==========
import { createRouter, createWebHistory } from 'vue-router'
import axios from 'axios' // 移到这里
import LoginView from '../views/LoginView.vue'
import AdminLayout from '../views/AdminLayout.vue'
import PortalLayout from '../views/PortalLayout.vue'
import DashboardView from '../views/DashboardView.vue'
import DevicesView from '../views/DevicesView.vue'
import SettingsView from '../views/SettingsView.vue'
import LogsView from '../views/LogsView.vue'
import BaselineView from '../views/BaselineView.vue'
import AlertsView from '../views/AlertsView.vue'
import OASystemView from '../views/OASystemView.vue'
import OAApprovalView from '../views/OAApprovalView.vue'
import OASourceCodeView from '../views/OASourceCodeView.vue'
import OAExpenseView from '../views/OAExpenseView.vue'
import CallbackView from '../views/CallbackView.vue'

// ========== 原有路由配置完全不变 ==========
const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'Login', component: LoginView },
  { path: '/login/callback', name: 'LoginCallback', component: CallbackView, meta: { requiresAuth: false } },
  {
    path: '/admin',
    component: AdminLayout,
    redirect: '/admin/dashboard',
    children: [
      { path: 'dashboard', name: 'AdminDashboard', component: DashboardView },
      { path: 'devices', name: 'AdminDevices', component: DevicesView },
      { path: 'baseline', name: 'AdminBaseline', component: BaselineView },
      { path: 'logs', name: 'AdminLogs', component: LogsView },
      { path: 'alerts', name: 'AdminAlerts', component: AlertsView },
      { path: 'settings', name: 'AdminSettings', component: SettingsView }
    ]
  },
  {
    path: '/portal',
    component: PortalLayout,
    redirect: '/portal/oa',
    children: [
      {
        path: 'oa',
        name: 'PortalOA',
        component: OASystemView,
        children: [
          { path: 'approval', name: 'OAApproval', component: OAApprovalView },
          { path: 'sourcecode', name: 'OASourceCode', component: OASourceCodeView },
          { path: 'expense', name: 'OAExpense', component: OAExpenseView }
        ]
      }
    ]
  },
  { path: '/dashboard', redirect: '/admin/dashboard' },
  { path: '/oa', redirect: '/portal/oa' },
  {
    path: '/alerts',
    name: 'Alerts',
    component: AlertsView,
    meta: { title: '异常告警' }
  },
  {
    path: '/baseline',
    name: 'Baseline',
    component: BaselineView,
    meta: { title: '行为基线' }
  },
  {
    path: '/devices',
    name: 'Devices',
    component: DevicesView,
    meta: { title: '设备管理' }
  },
  {
    path: '/logs',
    name: 'Logs',
    component: LogsView,
    meta: { title: '行为日志' }
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// ========== 【核心修复】合并为一个守卫，OA强制阻断+原有鉴权完美融合 ==========
router.beforeEach(async (to, from) => {
  const token = localStorage.getItem('sys_token')
  const role = localStorage.getItem('user_role')

  // -------------------------- 1. 优先判断：是否是OA相关路由（修正判断逻辑） --------------------------
  // 匹配所有OA路径：/oa、/portal/oa、/portal/oa/*
  const isOaRoute = to.path.startsWith('/oa') || to.path.startsWith('/portal/oa')
  
  if (isOaRoute) {
    // 【强制阻断逻辑】OA路由必须走严格的后端校验
    if (!token) {
      // 无token，直接阻断，重定向到登录页
      return { path: '/login', query: { redirect: to.fullPath } }
    }

    try {
      // 调用后端接口强制校验登录状态
      const res = await axios.get('/api/oa/check-login', {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 5000
      })
      if (res.data?.status === 'success' && res.data?.is_login) {
        // 登录校验通过，继续走后面的原有鉴权逻辑
        // 不直接return，让代码流到下面的原有逻辑
      } else {
        return { path: '/login', query: { redirect: to.fullPath } }
      }
    } catch (err) {
      console.error('OA登录校验失败：', err)
      localStorage.removeItem('sys_token')
      localStorage.removeItem('user_info')
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }

  // -------------------------- 2. 原有鉴权逻辑（完全保留，不做任何修改） --------------------------
  if (to.path !== '/login' && !token) {
    return '/login'
  } else if (to.path.startsWith('/admin') && role !== 'admin') {
    // 拦截非管理员访问 admin 页面
    return '/portal'
  } else {
    return true
  }
})

export default router