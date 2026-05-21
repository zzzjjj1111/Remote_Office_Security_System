<template>
  <div class="oa-container">
    <el-header class="oa-header">
      <div class="oa-title">企业办公OA系统</div>
      <div class="oa-user-info">
        <span>当前用户：{{ userInfo.name }}</span>
        <el-tag :type="trustTagType" style="margin-left: 15px;">信任分：{{ userInfo.trust_score }}分</el-tag>
        <el-button type="danger" text @click="logout" style="margin-left: 20px;">退出登录</el-button>
      </div>
    </el-header>

    <el-main class="oa-main">
      <!-- 风险提醒区域 -->
      <el-alert
        v-for="(risk, index) in riskList"
        :key="index"
        :title="risk.content"
        :type="risk.level === 'high' ? 'error' : 'warning'"
        show-icon
        style="margin-bottom: 20px;"
      />

      <!-- OA功能菜单 -->
      <el-row :gutter="20">
        <el-col :span="6" v-for="item in menuList" :key="item.name">
          <el-card class="menu-card" shadow="hover" @click="handleMenuClick(item)">
            <div class="menu-icon">{{ item.icon }}</div>
            <div class="menu-name">{{ item.name }}</div>
            <div class="menu-desc">{{ item.desc }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 工作时间配置（仅管理员可见） -->
      <el-card v-if="isAdmin" style="margin-top: 30px;">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 16px; font-weight: bold;">⏰ 工作时间配置</span>
            <el-button type="primary" size="small" @click="showWorkTimeDialog = true">修改时间</el-button>
          </div>
        </template>
        <div style="font-size: 14px; color: #606266;">
          当前工作时间：<el-tag type="success">{{ workTime.work_start_time }}</el-tag> 至 
          <el-tag type="success">{{ workTime.work_end_time }}</el-tag>
          <el-divider direction="vertical" />
          <span style="color: #909399;">非工作时间操作将被标记为异常</span>
        </div>
      </el-card>

      <!-- OA访问日志 -->
      <div class="log-area" style="margin-top: 40px;">
        <h3> 最近操作日志</h3>
        <el-table :data="logList" border style="width: 100%;" max-height="400">
          <el-table-column prop="operate_type" label="操作类型" width="150" />
          <el-table-column prop="operate_desc" label="操作描述" width="300" />
          <el-table-column prop="client_ip" label="访问IP" width="150" />
          <el-table-column prop="result" label="结果" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.result === 'success' ? 'success' : 'danger'">
                {{ scope.row.result === 'success' ? '成功' : '已阻断' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="操作时间" width="200" />
        </el-table>
      </div>
    </el-main>

    <!-- 操作表单弹窗 -->
    <el-dialog v-model="actionDialogVisible" :title="currentAction.name" width="600px">
      <el-form :model="actionForm" label-width="100px">
        <el-form-item label="操作描述">
          <el-input v-model="actionForm.detail" type="textarea" :rows="3" placeholder="请输入操作详情" />
        </el-form-item>
        <el-form-item label="目标文件" v-if="currentAction.needFile">
          <el-input v-model="actionForm.targetFile" placeholder="请输入文件名称（可选）" />
          <div style="font-size: 12px; color: #909399; margin-top: 5px;">
             提示：尝试输入"财务报表"、"核心源码"等敏感词可触发阻断
          </div>
        </el-form-item>
        <el-form-item label="紧急程度" v-if="currentAction.needUrgent">
          <el-radio-group v-model="actionForm.urgent">
            <el-radio label="normal">正常</el-radio>
            <el-radio label="urgent">加急</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="actionDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAction">提交</el-button>
      </template>
    </el-dialog>

    <!-- 工作时间修改弹窗 -->
    <el-dialog v-model="showWorkTimeDialog" title="修改工作时间" width="500px">
      <el-form :model="workTimeForm" label-width="120px">
        <el-form-item label="工作开始时间">
          <el-time-picker v-model="workTimeForm.start" format="HH:mm" value-format="HH:mm" placeholder="选择时间" />
        </el-form-item>
        <el-form-item label="工作结束时间">
          <el-time-picker v-model="workTimeForm.end" format="HH:mm" value-format="HH:mm" placeholder="选择时间" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showWorkTimeDialog = false">取消</el-button>
        <el-button type="primary" @click="updateWorkTime">保存</el-button>
      </template>
    </el-dialog>

    <!-- 操作结果提示 -->
    <el-dialog v-model="resultDialogVisible" title="操作结果" width="500px" :close-on-click-modal="false">
      <el-alert
        :title="resultMessage"
        :type="isBlocked ? 'error' : 'success'"
        show-icon
        :closable="false"
      />
      <div style="margin-top: 20px; font-size: 14px; color: #606266;">
        <p v-if="resultData"> 风险评估：</p>
        <ul v-if="resultData" style="line-height: 2;">
          <li>异常评分：{{ resultData.anomaly_score }}分</li>
          <li>风险等级：{{ resultData.risk_level === 'high' ? '高风险' : '低风险' }}</li>
          <li>工作时间：{{ resultData.is_work_time ? '✅ 工作时间内' : '⚠️ 非工作时间' }}</li>
          <li v-if="resultData.is_sensitive">敏感检测： 检测到敏感词</li>
        </ul>
        <p v-if="isBlocked" style="color: #f56c6c; margin-top: 10px;">
           该操作已被系统阻断，管理员已收到告警通知
        </p>
      </div>
      <template #footer>
        <el-button type="primary" @click="resultDialogVisible = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const router = useRouter()
const token = localStorage.getItem('sys_token')

// 基础数据
const userInfo = ref({ name: '', trust_score: 100 })
const isAdmin = ref(false)
const riskList = ref([])
const logList = ref([])

// 工作时间
const workTime = ref({ work_start_time: '09:30', work_end_time: '18:30' })
const showWorkTimeDialog = ref(false)
const workTimeForm = ref({ start: '09:30', end: '18:30' })

// 操作弹窗
const actionDialogVisible = ref(false)
const currentAction = ref({})
const actionForm = ref({ detail: '', targetFile: '', urgent: 'normal' })

// 结果弹窗
const resultDialogVisible = ref(false)
const resultMessage = ref('')
const resultData = ref(null)
const isBlocked = ref(false)

// 信任分标签样式
const trustTagType = computed(() => {
  const score = userInfo.value.trust_score || 0
  if (score >= 80) return 'success'
  if (score >= 50) return 'warning'
  return 'danger'
})

// OA功能菜单
const menuList = [
  { name: '审批流程', icon: '📝', desc: '提交/查看审批', code: 'approval', needFile: false, needUrgent: false },
  { name: '文件共享', icon: '📁', desc: '浏览/上传文件', code: 'file_share', needFile: true, needUrgent: false },
  { name: '日程管理', icon: '📅', desc: '查看/编辑日程', code: 'schedule', needFile: false, needUrgent: false },
  { name: '批量文件导出', icon: '📤', desc: '需信任分≥80', code: 'file_export', needFile: true, needUrgent: false },
  { name: '敏感文件查看', icon: '🔒', desc: '需信任分≥80', code: 'sensitive_view', needFile: false, needUrgent: false },
  { name: '审批加急', icon: '⚡', desc: '需信任分≥80', code: 'urgent_approval', needFile: false, needUrgent: true }
]

// 点击菜单
const handleMenuClick = (item) => {
  // 权限检查
  if (item.code === 'file_export' || item.code === 'sensitive_view' || item.code === 'urgent_approval') {
    if (userInfo.value.trust_score < 80) {
      ElMessage.warning(`此功能需信任分≥80，当前信任分：${userInfo.value.trust_score}`)
      return
    }
  }
  
  currentAction.value = item
  actionForm.value = { detail: '', targetFile: '', urgent: 'normal' }
  actionDialogVisible.value = true
}

// 提交操作
const submitAction = async () => {
  if (!actionForm.value.detail) {
    ElMessage.warning('请输入操作描述')
    return
  }
  
  try {
    const res = await axios.post('http://127.0.0.1:5000/api/oa/action', {
      action_type: currentAction.value.code,
      action_detail: actionForm.value.detail,
      target_file: actionForm.value.targetFile || ''
    }, {
      headers: { Authorization: `Bearer ${token}` }
    })
    
    if (res.data.status === 'success') {
      const data = res.data.data
      actionDialogVisible.value = false
      
      // 显示结果
      resultData.value = data
      isBlocked.value = data.is_blocked
      resultMessage.value = data.is_blocked 
        ? ' 操作已被系统阻断' 
        : '✅ 操作已成功记录'
      resultDialogVisible.value = true
      
      // 刷新日志
      getAccessLog()
    }
  } catch (err) {
    ElMessage.error('操作失败：' + (err.response?.data?.message || err.message))
  }
}

// 获取用户信息
const getUserInfo = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:5000/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (res.data.status === 'success') {
      userInfo.value = res.data.data
      isAdmin.value = res.data.data.position === '系统管理员'
    }
  } catch (err) {
    console.error('获取用户信息失败', err)
  }
}

// 获取风险提醒
const getRiskAlert = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:5000/api/oa/risk-alert', {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (res.data.status === 'success') {
      riskList.value = res.data.data.risk_list || []
    }
  } catch (err) {
    console.error('获取风险提醒失败')
  }
}

// 获取访问日志
const getAccessLog = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:5000/api/oa/access-log', {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (res.data.status === 'success') {
      logList.value = res.data.data.list || []
    }
  } catch (err) {
    console.error('获取日志失败')
  }
}

// 获取工作时间
const getWorkTime = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:5000/api/oa/work-time', {
      headers: { Authorization: `Bearer ${token}` }
    })
    if (res.data.status === 'success') {
      workTime.value = res.data.data
    }
  } catch (err) {
    console.error('获取工作时间失败')
  }
}

// 更新工作时间
const updateWorkTime = async () => {
  try {
    const res = await axios.post('http://127.0.0.1:5000/api/oa/work-time', {
      work_start_time: workTimeForm.value.start,
      work_end_time: workTimeForm.value.end
    }, {
      headers: { Authorization: `Bearer ${token}` }
    })
    
    if (res.data.status === 'success') {
      ElMessage.success('工作时间已更新')
      workTime.value = res.data.data
      showWorkTimeDialog.value = false
    }
  } catch (err) {
    ElMessage.error('更新失败：' + (err.response?.data?.message || err.message))
  }
}

// 退出登录
const logout = () => {
  localStorage.removeItem('sys_token')
  localStorage.removeItem('user_info')
  localStorage.removeItem('user_role')
  ElMessage.success('已退出登录')
  router.push('/login')
}

// 页面初始化
onMounted(() => {
  getUserInfo()
  getRiskAlert()
  getAccessLog()
  getWorkTime()
})
</script>

<style scoped>
.oa-container {
  height: 100vh;
  background-color: #f5f7fa;
}
.oa-header {
  background-color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 30px;
  border-bottom: 1px solid #e4e7ed;
}
.oa-title {
  font-size: 22px;
  font-weight: bold;
  color: #303133;
}
.oa-user-info {
  display: flex;
  align-items: center;
}
.oa-main {
  padding: 20px 30px;
}
.menu-card {
  text-align: center;
  cursor: pointer;
  margin-bottom: 20px;
  transition: all 0.3s;
}
.menu-card:hover {
  transform: translateY(-5px);
}
.menu-icon {
  font-size: 40px;
  margin-bottom: 10px;
}
.menu-name {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 5px;
}
.menu-desc {
  font-size: 12px;
  color: #909399;
}
.log-area h3 {
  margin-bottom: 15px;
  color: #303133;
}
</style>
