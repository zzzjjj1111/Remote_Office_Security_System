<template>
  <div class="portal-wrapper">
    <el-container style="height: 100vh;">
      <el-header class="portal-header">
        <div class="logo">基于行为基线的联动OA工作台 (受防护)</div>
        <div class="user-action">
          <span style="margin-right: 15px;">当前行为信任分: <el-tag :type="scoreType" effect="dark">{{ trustScore }}</el-tag></span>
          <el-button v-if="isAdmin" color="#626aef" plain @click="$router.push('/dashboard')">进入管理员控制台</el-button>
          <el-button type="danger" @click="logout">退出办公</el-button>
        </div>
      </el-header>
      
      <el-main class="portal-main">
        <div class="content-box">
          <router-view></router-view>
        </div>
      </el-main>
    </el-container>

    <!-- 浮动的终端行为模拟器 -->
    <el-tooltip content="测试/答辩使用：拉起底层 Agent 注入面板" placement="left">
      <el-button class="debugger-btn" type="warning" circle size="large" @click="drawerVisible = true">
        Bug
      </el-button>
    </el-tooltip>

    <el-drawer v-model="drawerVisible" title=" 终端仿真上报器" direction="rtl" size="40vw">
      <SimulatorView />
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import SimulatorView from './SimulatorView.vue'

const router = useRouter()
const isAdmin = ref(localStorage.getItem('user_role') === 'admin')
const trustScore = ref(100)
const drawerVisible = ref(false)
let timer = null

const scoreType = computed(() => {
  if (trustScore.value >= 80) return 'success'
  if (trustScore.value >= 50) return 'warning'
  return 'danger'
})

const fetchScore = async () => {
  const token = localStorage.getItem('sys_token')
  if (!token) return
  try {
    const res = await axios.get('http://127.0.0.1:5000/api/auth/me', {
      headers: { 'Authorization': 'Bearer ' + token }
    })
    trustScore.value = res.data.data.trust_score
  } catch(e) {}
}

const logout = () => {
  localStorage.removeItem('sys_token')
  localStorage.removeItem('user_role')
  router.push('/login')
}

onMounted(() => {
  fetchScore()
  timer = setInterval(fetchScore, 5000)
})

onUnmounted(() => {
  clearInterval(timer)
})
</script>

<style scoped>
.portal-wrapper {
  background-color: #f0f2f5;
}
.portal-header {
  background-color: #1d2129;
  color: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.logo {
  font-size: 18px;
  font-weight: bold;
}
.portal-main {
  padding: 40px;
  height: calc(100vh - 60px);
  overflow-y: auto;
}
.content-box {
  max-width: 1200px;
  margin: 0 auto;
}
.debugger-btn {
  position: fixed;
  right: 30px;
  bottom: 50px;
  z-index: 2000;
  box-shadow: 0 4px 12px rgba(230, 162, 60, 0.4);
}
</style>
