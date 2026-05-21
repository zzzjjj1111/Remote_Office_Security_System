<!-- CallbackView.vue (完全替换现有内容，极简实现) -->
<template>
  <div class="callback-container">
    <el-result
      v-if="status === 'loading'"
      icon="info"
      title="登录验证中..."
      sub-title="正在核实企业微信身份，请稍候..."
    />
    <el-result
      v-else-if="status === 'error'"
      icon="error"
      title="登录失败"
      :sub-title="errorMsg"
    >
      <template #extra>
        <el-button type="primary" @click="goBack">返回重试</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const status = ref('loading')
const errorMsg = ref('')

onMounted(async () => {
  const code = route.query.code
  // 从路由中获取登录前要跳转的地址
  const redirectPath = route.query.redirect || '/portal'

  if (!code) {
    status.value = 'error'
    errorMsg.value = '缺失企业微信授权 Code！'
    return
  }

  try {
    const res = await axios.post('http://127.0.0.1:5000/api/auth/wechat/callback', { code: code })
    if (res.data.status === 'success') {
      localStorage.setItem('sys_token', res.data.access_token)
      localStorage.setItem('user_info', JSON.stringify(res.data.data))
      localStorage.setItem('user_role', 'user')
      ElMessage.success('企业微信登录成功！')

      // ========== 【修改后的跳转逻辑：兼容OA重定向】 ==========
      router.push(redirectPath)
      // ========================================================
    } else {
      status.value = 'error'
      errorMsg.value = res.data.message || '登录验证失败'
    }
  } catch (err) {
    status.value = 'error'
    errorMsg.value = err.response?.data?.message || '网络请求错误'
  }
})

const goBack = () => {
  router.push('/login')
}
</script>

<style scoped>
.callback-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
}
</style>