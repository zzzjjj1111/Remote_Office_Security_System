<template>
  <div class="login-container">
    <el-card class="login-card" shadow="always">
      <div class="login-header">
        <h2>基于行为基线的防护系统</h2>
        <p>多维度感知 · 动态信任 · 异常阻断</p>
      </div>
      <el-form label-position="top" style="margin-top: 40px;">
        <el-form-item label="企业账号" class="form-item-label">
          <el-input
            v-model="username"
            placeholder="请输入员工账号 / Admin"
            size="large"
            class="large-input"
          />
        </el-form-item>
        <el-form-item label="密码" class="form-item-label">
          <el-input
            v-model="password"
            type="password"
            placeholder="请输入密码"
            show-password
            size="large"
            class="large-input"
          />
        </el-form-item>
        <el-button
          type="primary"
          @click="handleLogin"
          :loading="loading"
          size="large"
          class="login-btn"
        >
          安全登录验证
        </el-button>

        <!-- 修复：新增企业微信扫码登录入口 -->
        <el-divider content-position="center">或</el-divider>
        <div style="text-align: center;">
          <el-button
            type="primary"
            plain
            size="large"
            @click="handleWechatLogin"
            :loading="wechatLoading"
            style="width: 100%;"
          >
            <el-icon><ChatDotRound /></el-icon>
            企业微信扫码登录
          </el-button>
        </div>

        <div class="login-tip">
          Tip: admin 登录进入控制台, user 登录进入工作台
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
// 修复：导入企业微信图标
import { ChatDotRound } from '@element-plus/icons-vue'

const route = useRoute()

// 原有变量（完全保留，不修改）
const username = ref('admin')
const password = ref('password123')
const loading = ref(false) // 原有账号密码登录的loading
const router = useRouter()

// 修复：新增企业微信登录独立loading，不与原有重复
const wechatLoading = ref(false)

// LoginView.vue 里的 handleLogin 完整修复版
const handleLogin = async () => {
    loading.value = true
    try {
        // 修复：使用相对路径，通过Vite代理访问后端，避免CORS跨域问题
        const res = await axios.post('/api/auth/login', {
            username: username.value,
            password: password.value
        })

        // 1. 校验后端返回是否成功
        if (res.data?.status !== 'success') {
            ElMessage.error(res.data?.message || '登录验证失败')
            return
        }

        // 2. 保存token、用户信息、角色（和你原有逻辑完全兼容）
        const token = res.data.access_token
        localStorage.setItem('sys_token', token)
        localStorage.setItem('user_info', JSON.stringify(res.data.data || {}))
        const userRole = username.value === 'admin' ? 'admin' : 'user'
        localStorage.setItem('user_role', userRole)

        ElMessage.success('身份环境核验通过')

        // 3. 核心修复：优先跳redirect参数指定的地址，没有再按角色跳转
        const targetPath = route.query.redirect || (userRole === 'admin' ? '/admin' : '/portal/oa')
        // 执行跳转
        router.push(targetPath)

    } catch(err) {
        // 修复：明确报错提示，不会静默失败
        console.error('登录异常：', err)
        
        // 【新增】检查是否是被阻断
        const errorCode = err.response?.data?.code
        if (errorCode === 'USER_BLOCKED') {
            ElMessageBox.alert(
                `<div style="text-align: center; padding: 20px;">
                   <div style="font-size: 60px; margin-bottom: 15px;">🚫</div>
                   <div style="font-size: 24px; font-weight: bold; color: #f56c6c; margin-bottom: 15px;">账号已被阻断</div>
                   <div style="font-size: 16px; color: #666; line-height: 1.8; margin-bottom: 20px;">
                     ${err.response?.data?.message || '您的账号已被管理员阻断，无法登录系统'}
                   </div>
                   <div style="font-size: 14px; color: #999; background: #f5f7fa; padding: 15px; border-radius: 8px;">
                     📞 请联系IT支持部门解除阻断<br/>
                     电话：ext. 8888<br/>
                     邮箱：it-support@company.com
                   </div>
                 </div>`,
                '登录被拒绝',
                {
                    dangerouslyUseHTMLString: true,
                    confirmButtonText: '我知道了',
                    type: 'error',
                    customStyle: {
                        width: '500px',
                        borderRadius: '16px'
                    }
                }
            )
            return
        }
        
        // 显示详细错误信息
        const errorMsg = err.response?.data?.message || err.response?.data?.msg || err.message || '网络连接或验证失败'
        console.error('错误详情：', err.response?.data)
        ElMessage.error(errorMsg)
    } finally {
        loading.value = false
    }
}

// 模拟企业微信扫码登录逻辑（用于演示环境）
const handleWechatLogin = async () => {
  wechatLoading.value = true
  try {
    // 模拟延迟，营造真实扫码体验
    await new Promise(resolve => setTimeout(resolve, 1500))
    
    // 【修复】优先使用用户输入的账号进行登录，如果没有输入则默认使用 admin
    let loginAccount = 'admin'
    if (username.value && username.value.trim() !== '') {
      // 如果输入的是纯数字（如 20），自动补全为 work_wechat_id 格式 (user_0020)
      if (/^\d+$/.test(username.value)) {
        loginAccount = `user_${username.value.padStart(4, '0')}`
      } else {
        loginAccount = username.value
      }
    }
    
    // 调用登录接口获取 Token
    const res = await axios.post('/api/auth/login', {
      username: loginAccount, 
      password: 'password123' // 统一默认密码
    })
    
    if (res.data.status === 'success') {
      const userInfo = res.data.data.user
      // 【修复】根据用户 ID 判断角色，1 是管理员，其他是普通员工
      const role = userInfo.id === 1 ? 'admin' : 'user'
      
      // 保存登录凭证
      localStorage.setItem('sys_token', res.data.access_token)
      localStorage.setItem('user_info', JSON.stringify(userInfo))
      localStorage.setItem('user_role', role)
      
      // 显示大号、高醒目的成功提示框
      ElMessageBox.alert(
        `<div style="text-align: center; padding: 20px;">
           <div style="font-size: 60px; margin-bottom: 15px;">✅</div>
           <div style="font-size: 28px; font-weight: bold; color: #16a34a; margin-bottom: 10px;">企业微信登录成功</div>
           <div style="font-size: 18px; color: #666;">欢迎回来，${userInfo.name}</div>
           <div style="font-size: 14px; color: #999; margin-top: 15px;">系统将在 3 秒后自动跳转...</div>
         </div>`,
        '安全认证通过',
        {
          dangerouslyUseHTMLString: true,
          confirmButtonText: '立即跳转',
          customStyle: {
            width: '450px',
            borderRadius: '16px'
          },
          callback: () => {
            performRedirect(role)
          }
        }
      )
      
      // 3 秒后自动执行跳转，并关闭当前可能残留的 MessageBox
      setTimeout(() => {
        performRedirect(role)
      }, 3000)
    }
  } catch (err) {
    console.error('模拟登录异常：', err)
    ElMessage.error(`登录失败：${err.response?.data?.message || err.message}`)
  } finally {
    wechatLoading.value = false
  }
}

// 【新增】统一的跳转函数，确保弹窗先关闭再跳转
const performRedirect = (role) => {
  // 强制关闭所有正在显示的 MessageBox
  ElMessageBox.close()
  
  const targetPath = role === 'admin' ? '/admin/dashboard' : '/portal/oa'
  // 使用 nextTick 确保 DOM 状态更新后再跳转，避免路由守卫冲突
  setTimeout(() => {
    router.push(targetPath)
  }, 100)
}
</script>

<style scoped>
/* 原有样式完全保留，不做任何修改 */
.login-container {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #06f6af 0%, #069a6e 100%);
}

.login-card {
  width: 620px;
  padding: 55px 65px;
  border-radius: 18px;
  box-shadow: 0 22px 45px rgba(0, 0, 0, 0.18) !important;
  border: none;
}

.login-header {
  text-align: center;
  margin-bottom: 50px;
}
.login-header h2 {
  color: #2d3436;
  margin-bottom: 14px;
  font-size: 34px;
  font-weight: 700;
  letter-spacing: 2px;
}
.login-header p {
  color: #636e72;
  font-size: 19px;
  margin: 0;
  letter-spacing: 2px;
}

.form-item-label {
  font-size: 30px;
  font-weight: 600;
  color: #495057;
  margin-bottom: 12px;
}

.large-input {
  height: 60px;
}
:deep(.el-input__wrapper) {
  height: 60px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
  border-radius: 10px;
}
:deep(.el-input__inner) {
  font-size: 22px;
  padding: 0 18px;
}
:deep(.el-input__wrapper:hover) {
  box-shadow: 0 3px 10px rgba(26, 147, 111, 0.28);
}

.login-btn {
  width: 100%;
  margin-top: 40px;
  height: 60px;
  font-size: 22px;
  font-weight: bold;
  letter-spacing: 2px;
  background-color: #1a936f;
  border-color: #1a936f;
}
:deep(.el-button--primary:hover) {
  background-color: #0f766e;
  border-color: #0f766e;
}

.login-tip {
  text-align: center;
  margin-top: 30px;
  color: #909399;
  font-size: 17px;
}
</style>