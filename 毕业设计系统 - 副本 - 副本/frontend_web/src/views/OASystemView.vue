4<template>
  <div class="oa-container">
    <el-card class="oa-card">
      <template #header>
        <div class="card-header">
          <span class="page-title"> 内部业务系统集群 (网关保护边界内)</span>
          
          <!-- 【新增】Agent状态指示器 -->
          <el-tag 
            :type="agentRunning ? 'success' : 'danger'" 
            effect="dark"
            style="marginRight: '10px'"
          >
            <el-icon v-if="agentCheckLoading" class="is-loading"><Loading /></el-icon>
            <span v-else>{{ agentRunning ? '🟢 Agent运行中' : '🔴 Agent未启动' }}</span>
          </el-tag>
          
          <!-- 【新增】显示当前权限等级 -->
          <el-tag :type="privilegeLevelType" effect="dark" size="large">
            {{ privilegeLevelText }}
          </el-tag>
          <!-- 【新增】显示当前登录用户信息 -->
          <div v-if="userInfo" class="user-info">
            <el-avatar :size="40" style="background-color: #409eff; margin-right: 12px; font-size: 18px">
              {{ userInfo.name?.charAt(0) || 'U' }}
            </el-avatar>
            <div class="user-details">
              <div class="user-name">{{ userInfo.name }}</div>
              <div class="user-meta">
                <el-tag size="default" type="info">{{ userInfo.department }}</el-tag>
                <el-tag size="default" type="warning">{{ userInfo.position }}</el-tag>
                <el-tag size="default" type="success">信任分: {{ trustScore }}</el-tag>
              </div>
            </div>
          </div>
        </div>
      </template>

      <div v-if="loading" class="loading-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <p>网关验证中...</p>
      </div>

      <!-- 【修改】移除硬阻断，改为全量展示，但加锁和引导 -->
      <div class="app-grid">
        <!-- 审批系统：所有人可见，低信任加锁 -->
        <el-card
          shadow="hover"
          class="app-item"
          :class="{ 'locked-item': trustScore < 50 || !agentRunning }"
          @click="handleApproval"
        >
          <el-icon size="40" :color="(trustScore >= 50 && agentRunning) ? '#409eff' : '#909399'"><Document /></el-icon>
          <h3>协同审批系统</h3>
          <p>核心业务</p>
          <el-tag v-if="!agentRunning" type="danger" size="small">需启动Agent</el-tag>
          <el-tag v-else-if="trustScore < 50" type="info" size="small">信任分≥50分解锁</el-tag>
          <el-tag v-else-if="trustScore >= 80" type="success" size="small">信任分≥50分，已解锁加急通道</el-tag>
          <el-tag v-else type="success" size="small">信任分≥50分，已解锁</el-tag>
        </el-card>

        <!-- 源码仓库：高密级，需 >=80 -->
        <el-card
          shadow="hover"
          class="app-item"
          :class="{ 'locked-item': trustScore < 80 || !agentRunning }"
          @click="handleSourceCode"
        >
          <el-icon size="40" :color="(trustScore >= 80 && agentRunning) ? '#67c23a' : '#909399'"><Monitor /></el-icon>
          <h3>内部源码仓库</h3>
          <p>高密级</p>
          <el-tag v-if="!agentRunning" type="danger" size="small">需启动Agent</el-tag>
          <el-tag v-else-if="trustScore < 80" type="warning" size="small">信任分≥80分解锁</el-tag>
          <el-tag v-else type="success" size="small">信任分≥80分，已解锁克隆权限</el-tag>
        </el-card>

        <!-- 财务报销：需 >=50 -->
        <el-card
          shadow="hover"
          class="app-item"
          :class="{ 'locked-item': trustScore < 50 || !agentRunning }"
          @click="handleExpense"
        >
          <el-icon size="40" :color="(trustScore >= 50 && agentRunning) ? '#e6a23c' : '#909399'"><Money /></el-icon>
          <h3>财务报销系统</h3>
          <p>敏感业务</p>
          <el-tag v-if="!agentRunning" type="danger" size="small">需启动Agent</el-tag>
          <el-tag v-else-if="trustScore < 50" type="info" size="small">信任分≥50分解锁</el-tag>
          <el-tag v-else type="success" size="small">信任分≥50分，已解锁报销权限</el-tag>
        </el-card>
      </div>

      <el-divider>当前位置：隧道内部</el-divider>
      <router-view />

    </el-card>

    <!-- 【新增：选题文档要求】非阻断式价值引导弹窗 -->
    <el-dialog
      v-model="guideDialogVisible"
      title="🔒 远程办公安全防护提示"
      width="500px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <div class="guide-content">
        <el-alert
          title="检测到您的终端信任分较低或未启用安全探针"
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 20px;"
        />

        <h4>登录防护系统即可获得以下权益：</h4>
        <ul>
          <li>✅ 实时查看个人远程办公安全风险提醒</li>
          <li>✅ 规避敏感操作误追责风险</li>
          <li>✅ <strong>解锁 OA 高级功能</strong>（如批量文件导出、跨部门加急审批）</li>
        </ul>

        <el-divider />

        <div class="trust-score-showcase">
          <div class="score-item">
            <el-tag type="danger">信任分 &lt; 50</el-tag>
            <span>仅可浏览 OA 首页</span>
          </div>
          <div class="score-item">
            <el-tag type="warning">信任分 50-79</el-tag>
            <span>解锁基础业务办理</span>
          </div>
          <div class="score-item">
            <el-tag type="success">信任分 ≥ 80</el-tag>
            <span>解锁全部高级功能</span>
          </div>
        </div>
      </div>

      <template #footer>
        <el-button @click="guideDialogVisible = false">稍后登录 (仅浏览)</el-button>
        <el-button type="primary" @click="goToLogin">立即登录防护系统</el-button>
      </template>
    </el-dialog>

    <!-- 【新增】Agent启动引导对话框 -->
    <el-dialog
      v-model="showStartAgentDialog"
      title="🔒 安全客户端未运行"
      width="600px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <div style="padding: 10px;">
        <el-alert
          title="检测到您的终端安全客户端（Agent）未运行"
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 20px;"
        />

        <div style="background: #f5f7fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
          <h4 style="margin-top: 0; color: #303133;">⚠️ 功能限制说明</h4>
          <ul style="line-height: 2; color: #606266;">
            <li>所有OA功能已暂时锁定</li>
            <li>无法访问审批、源码、报销等系统</li>
            <li>需要启动Agent后才能正常使用</li>
          </ul>
        </div>

        <div v-if="startInstructions" style="background: #fff; border: 1px solid #dcdfe6; padding: 15px; border-radius: 8px; margin-bottom: 20px; white-space: pre-line; line-height: 1.8;">
          {{ startInstructions }}
        </div>

        <el-divider />

        <div style="text-align: center;">
          <el-button 
            type="primary" 
            size="large"
            @click="handleStartAgent"
            style="width: 200px; font-size: 16px;"
          >
            📥 下载启动脚本
          </el-button>
          
          <el-button 
            size="large"
            @click="refreshAgentStatus"
            style="width: 200px; font-size: 16px; margin-left: 10px;"
          >
            🔄 刷新状态
          </el-button>
        </div>

        <div style="margin-top: 20px; padding: 15px; background: #fef0f0; border-radius: 8px; border-left: 4px solid #f56c6c;">
          <p style="margin: 0; color: #f56c6c; font-weight: bold;">⚠️ 重要提示：</p>
          <p style="margin: 10px 0 0 0; color: #606266; font-size: 14px;">
            下载的脚本需要在您的电脑上运行。运行后请保持命令行窗口开启，关闭窗口将停止监控。
          </p>
        </div>
      </div>

      <template #footer>
        <el-button @click="showStartAgentDialog = false">稍后处理</el-button>
        <el-button type="primary" @click="handleStartAgent">立即下载并启动</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { Document, Monitor, Money, Loading } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const hasAccess = ref(false)
const loading = ref(true)
const trustScore = ref(0)
const guideDialogVisible = ref(false)
const userInfo = ref(null)
// 【新增】Agent状态
const agentRunning = ref(false)
const agentCheckLoading = ref(false)
const showStartAgentDialog = ref(false)
const startInstructions = ref('')

// 【新增】计算权限等级文本
const privilegeLevelType = computed(() => {
  if (trustScore.value >= 80) return 'success'
  if (trustScore.value >= 50) return 'warning'
  return 'danger'
})
const privilegeLevelText = computed(() => {
  if (trustScore.value >= 80) return '🔓 全功能开放'
  if (trustScore.value >= 50) return '⚠️ 基础功能开放'
  return '🔒 浏览模式'
})

const checkAccess = async () => {
    loading.value = true
    try {
        const token = localStorage.getItem('sys_token')
        if (!token) {
            // 【修改】无Token时，不直接404，而是展示引导弹窗
            trustScore.value = 0
            hasAccess.value = false
            guideDialogVisible.value = true
            return
        }

        const res = await axios.get('http://127.0.0.1:5000/api/auth/me', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
        const score = res.data.data.trust_score
        trustScore.value = score
        userInfo.value = res.data.data // 保存用户完整信息
        hasAccess.value = true // 【修改】始终允许进入页面，只是功能加锁

        // 【新增】检查Agent运行状态
        await checkAgentStatus()

        // 如果分数过低，弹出提示但不踢出
        if (score < 50) {
            ElMessage.warning('当前信任分较低，部分高级功能已锁定')
        }
    } catch(e) {
        hasAccess.value = false
        trustScore.value = 0
        guideDialogVisible.value = true // 出错也弹出引导
    } finally {
        loading.value = false
    }
}

// 【新增】检查Agent运行状态
const checkAgentStatus = async () => {
    agentCheckLoading.value = true
    try {
        const token = localStorage.getItem('sys_token')
        const response = await axios.get('http://127.0.0.1:5000/api/agent/check-status', {
            headers: { 'Authorization': `Bearer ${token}` }
        })
        
        if (response.data.code === 200) {
            const data = response.data.data
            agentRunning.value = data.is_running
            
            // 【核心修复】检查是否为白名单用户
            if (data.is_whitelisted) {
                console.log('✅ [Agent白名单] 当前用户为管理员白名单，无需启动Agent')
                ElMessage.success({
                    message: `✅ 管理员白名单用户（${data.whitelist_reason}），无需启动Agent`,
                    duration: 3000,
                    showClose: true
                })
                return  // 白名单用户直接返回，不显示启动对话框
            }
            
            if (!agentRunning.value) {
                // Agent未运行，显示启动对话框
                showStartAgentDialog.value = true
                ElMessage.warning({
                    message: '⚠️ 检测到安全客户端未运行，所有功能已锁定',
                    duration: 5000,
                    showClose: true
                })
            }
        }
    } catch (e) {
        console.error('检查Agent状态失败:', e)
        agentRunning.value = false
        showStartAgentDialog.value = true
    } finally {
        agentCheckLoading.value = false
    }
}

// 【新增】获取启动脚本
const handleStartAgent = async () => {
    try {
        const token = localStorage.getItem('sys_token')
        const response = await axios.post('http://127.0.0.1:5000/api/agent/start-script', {}, {
            headers: { 'Authorization': `Bearer ${token}` }
        })
        
        if (response.data.code === 200) {
            startInstructions.value = response.data.data.instructions
            
            // 自动下载脚本
            window.open(`http://127.0.0.1:5000${response.data.data.script_url}`, '_blank')
            
            ElMessage.success('启动脚本已下载，请按照说明运行')
        }
    } catch (e) {
        console.error('获取启动脚本失败:', e)
        ElMessage.error('获取启动脚本失败，请联系IT部门')
    }
}

// 【新增】刷新Agent状态
const refreshAgentStatus = async () => {
    await checkAgentStatus()
    if (agentRunning.value) {
        ElMessage.success('✅ Agent已正常运行，功能已解锁')
        showStartAgentDialog.value = false
    } else {
        ElMessage.warning('Agent仍未检测到活动，请确保已启动脚本')
    }
}

const goToLogin = () => {
    guideDialogVisible.value = false
    router.push('/login')
}

const handleApproval = () => {
    if (!agentRunning.value) {
        ElMessage.warning('请先启动安全客户端（Agent）后再使用此功能')
        showStartAgentDialog.value = true
        return
    }
    if (trustScore.value < 50) {
        ElMessage.warning('信任分不足 50，无法使用审批功能，请先提升信任分')
        return
    }
    router.push('/portal/oa/approval')
}
const handleSourceCode = () => {
    if (!agentRunning.value) {
        ElMessage.warning('请先启动安全客户端（Agent）后再使用此功能')
        showStartAgentDialog.value = true
        return
    }
    if (trustScore.value < 80) {
        ElMessage.warning('源码仓库为高密级资源，需信任分 ≥ 80')
        return
    }
    router.push('/portal/oa/sourcecode')
}
const handleExpense = () => {
    if (!agentRunning.value) {
        ElMessage.warning('请先启动安全客户端（Agent）后再使用此功能')
        showStartAgentDialog.value = true
        return
    }
    if (trustScore.value < 50) {
        ElMessage.warning('信任分不足 50，无法使用报销功能')
        return
    }
    router.push('/portal/oa/expense')
}

onMounted(() => {
    checkAccess()
})

</script>

<style scoped>
.oa-container {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
/* 【新增】页面标题样式 */
.page-title {
  font-size: 20px;  /* 【调整】标题字体大小 */
  font-weight: bold;
  color: #303133;
}
/* 【新增】用户信息样式 */
.user-info {
  display: flex;
  align-items: center;
  margin-left: 20px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
.user-details {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.user-name {
  font-size: 16px;  /* 【调整这里】用户名大小 */
  font-weight: bold;
  color: #303133;
  line-height: 1.2;
}
.user-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.app-grid {
  display: flex;
  justify-content: space-around;
  margin-top: 20px;
}
.app-item {
  width: 250px;
  text-align: center;
  cursor: pointer;
  transition: transform 0.2s, opacity 0.2s;
}
/* 【新增】加锁样式 */
.locked-item {
  opacity: 0.6;
  cursor: not-allowed;
}
.locked-item:hover {
  transform: none !important;
}

.app-item:hover {
  transform: translateY(-5px);
}
.app-item h3 {
  margin: 15px 0 5px;
  font-size: 20px;  /* 【调整】系统名称字体大小，原来默认约18px */
}
.app-item p {
  color: #999;
  font-size: 16px;  /* 【调整】副标题字体大小，原来14px */
}
/* 【新增】权限标签字体大小 */
.app-item .el-tag {
  font-size: 14px;  /* 【调整】标签文字大小，Element Plus默认约12px */
  padding: 6px 12px;  /* 调整标签内边距，让标签更饱满 */
}
.loading-state, .deny-state {
  text-align: center;
  padding: 50px;
}
.is-loading {
  font-size: 40px;
  color: #409eff;
  margin-bottom: 20px;
}
/* 【新增】引导弹窗样式 */
.guide-content ul {
  text-align: left;
  line-height: 2;
}
.trust-score-showcase {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.score-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  background-color: #f5f7fa;
  border-radius: 4px;
}
</style>