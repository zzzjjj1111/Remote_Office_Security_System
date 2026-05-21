<template>
  <el-container class="layout-container">
    <el-aside width="220px" class="aside-menu">
      <div class="logo-box">
        <h3> 零信任防护</h3>
      </div>
      <el-menu
        active-text-color="#409eff"
        background-color="#304156"
        text-color="#bfcbd9"
        :default-active="$route.path"
        router
        class="el-menu-vertical"
      >
        <el-menu-item index="/dashboard">
          <span>监控大屏中心</span>
        </el-menu-item>
        <el-menu-item index="/oa">
          <span>模拟 OA 系统</span>
        </el-menu-item>
        <el-menu-item index="/simulator">
          <span>终端行为模拟器</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <span>当前用户信任值：<el-tag :type="scoreType" size="large">{{ currentScore }} 分</el-tag></span>
        </div>
        <div class="header-right">
          <el-button type="danger" size="small" @click="logout" plain>退出登录</el-button>
        </div>
      </el-header>
      
      <el-main class="main-content">
        <!-- 路由出口 -->
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const currentScore = ref(100)

const scoreType = computed(() => {
  if (currentScore.value >= 80) return 'success'
  if (currentScore.value >= 50) return 'warning'
  return 'danger'
})

const fetchUserInfo = async () => {
  const token = localStorage.getItem('sys_token')
  if (!token) return router.push('/login')
  
  try {
    const res = await axios.get('http://127.0.0.1:5000/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (res.data.status === 'success') {
      // 【临时修改】强制设置为100分，用于验证OA系统
      currentScore.value = 100
      // currentScore.value = res.data.data.trust_score
    }
  } catch (e) {
    console.warn('获取用户信息失败', e)
  }
}

onMounted(() => {
  fetchUserInfo()
  // 每隔5秒刷新一次分数，展现动态基线的调整效果
  setInterval(fetchUserInfo, 5000)
})

const logout = () => {
  localStorage.removeItem('sys_token')
  localStorage.removeItem('user_info')
  router.push('/login')
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
  width: 100vw;
}
.aside-menu {
  background-color: #304156;
  color: white;
}
.logo-box {
  height: 60px;
  line-height: 60px;
  text-align: center;
  background-color: #2b3643;
  color: #fff;
}
.el-menu-vertical {
  border-right: none;
}
.header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0,21,41,0.08);
}
.main-content {
  background-color: #f0f2f5;
  padding: 20px;
}
</style>
