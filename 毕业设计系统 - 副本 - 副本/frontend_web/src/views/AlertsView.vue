<template>
  <div style="padding: 20px; font-size: 16px;">
    <el-card shadow="never">
      <template #header>
        <div class="header-title">
          <span style="font-size: 18px; font-weight: bold;">异常告警事件处理</span>
        </div>
      </template>

      <div style="margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 15px; align-items: center;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 16px; color: #606266;">风险等级:</span>
          <el-select v-model="filterRisk" placeholder="全部" style="width: 120px; font-size: 16px;">
            <el-option label="全部" value="" />
            <el-option label="高风险" value="高风险" />
            <el-option label="中风险" value="中风险" />
            <el-option label="低风险" value="低风险" />
          </el-select>
        </div>

        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 16px; color: #606266;">处理状态:</span>
          <el-select v-model="filterStatus" placeholder="全部" style="width: 120px; font-size: 16px;">
            <el-option label="全部" value="" />
            <el-option label="待处理" value="待处理" />
            <el-option label="已处置" value="已处置" />
          </el-select>
        </div>

        <el-input v-model="searchKeyword" placeholder="搜索警告ID、操作人..." style="width: 280px; font-size: 16px;">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <button class="custom-btn" @click="handleFilter" style="margin-left: 10px; font-size: 14px;">
          <el-icon style="margin-right: 4px"><Search /></el-icon> 筛选告警
        </button>

        <button class="custom-btn" @click="handleBatchProcess" :disabled="!selectedRows.length" :style="selectedRows.length ? '' : 'opacity: 0.6; cursor: not-allowed;'">
          批量标记为误报
        </button>

        <button class="custom-btn" @click="refreshData" style="margin-left: auto; background-image: linear-gradient(30deg, #1890ff, #096dd9);">
          <el-icon style="margin-right: 4px"><Refresh /></el-icon> 刷新数据
        </button>
      </div>

      <el-table
        :data="paginatedData"
        style="width: 100%"
        border
        header-align="center"
        @selection-change="handleSelectionChange"
        :header-cell-style="{ fontSize: '16px', fontWeight: 'bold', backgroundColor: '#f5f7fa', textAlign: 'center' }"
        :cell-style="{ fontSize: '15px', padding: '12px 8px' }"
      >
        <el-table-column type="selection" width="40" align="center" />
        <el-table-column prop="alertId" label="告警编号" width="120" />
        <!-- 修复：确保发现时间列正确绑定并显示 -->
        <el-table-column prop="time" label="发现时间" width="180">
          <template #default="scope">
            <span style="font-size: 14px;">{{ scope.row.time || '暂无时间' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="level" label="风险等级" width="100" align="center">
          <template #default="scope">
            <el-tag
              :type="scope.row.level === '高风险' ? 'danger' : (scope.row.level === '中风险' ? 'warning' : 'info')"
              effect="plain" size="default"
            >
              {{ scope.row.level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="告警类型/触发规则" min-width="320">
          <template #default="scope">
            <span style="font-weight: 500; font-size: 15px;">{{ scope.row.type }}</span>
            <div style="font-size: 13px; color: #999; margin-top: 4px;">{{ scope.row.rule }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="user" label="相关当事人" width="120" />
        <el-table-column prop="contextInfo" label="上下文环境" width="160">
          <template #default="scope">
            <div v-if="scope.row.networkType" style="font-size: 13px;">
              <el-tag :type="getNetworkTypeTag(scope.row.networkType)" size="default" style="margin-right: 4px;">
                {{ getNetworkTypeText(scope.row.networkType) }}
              </el-tag>
              <span style="color: #606266; font-size: 14px;">{{ scope.row.locationHint }}</span>
            </div>
            <span v-else style="color: #909399; font-size: 14px;">-</span>
          </template>
        </el-table-column>
        <el-table-column label="折扣" width="80" align="center">
          <template #default="scope">
            <el-tag v-if="scope.row.discountFactor && scope.row.discountFactor < 1.0" type="success" size="default">
              {{ (scope.row.discountFactor * 100).toFixed(0) }}%
            </el-tag>
            <span v-else style="color: #909399;">-</span>
          </template>
        </el-table-column>
        <el-table-column label="推送通知" width="100" align="center">
          <template #default="scope">
            <el-tag v-if="scope.row.level === '高风险'" type="danger" size="default">
              已推送
            </el-tag>
            <el-tag v-else-if="scope.row.level === '中风险'" type="warning" size="default">
              已推送
            </el-tag>
            <el-tag v-else type="info" size="default">
              已通知
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="阻断结果" width="120" align="center">
          <template #default="scope">
            <el-tag v-if="scope.row.action === '阻断隔离' && scope.row.executionStatus === 'executed'" type="danger" size="default">
              ✅ 已执行
            </el-tag>
            <el-tag v-else-if="scope.row.action === '阻断隔离' && scope.row.executionStatus === 'pending'" type="warning" size="default">
              ⏳ 执行中
            </el-tag>
            <el-tag v-else-if="scope.row.action === '阻断隔离' && scope.row.executionStatus === 'failed'" type="info" size="default">
              ❌ 失败
            </el-tag>
            <el-tag v-else-if="scope.row.level === '高风险'" type="warning" size="default">
              待执行
            </el-tag>
            <span v-else style="color: #909399;">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="处理状态" width="100" align="center">
          <template #default="scope">
            <el-tag :type="scope.row.status === '待处理' ? 'danger' : 'success'" effect="dark" size="default">
              {{ scope.row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <!-- 【新增】用户决策状态列 -->
        <el-table-column label="用户决策" width="120" align="center">
          <template #default="scope">
            <el-tag v-if="scope.row.userDecision === 'user_confirmed'" type="success" size="default">
              已确认
            </el-tag>
            <el-tag v-else-if="scope.row.userDecision === 'user_cancelled'" type="info" size="default">
              已取消
            </el-tag>
            <el-tag v-else-if="scope.row.userDecision === 'pending_review'" type="warning" size="default">
              待审批
            </el-tag>
            <span v-else style="color: #909399;">-</span>
          </template>
        </el-table-column>
        <el-table-column label="处置操作" align="center" width="260" fixed="right">
          <template #default="scope">
            <template v-if="scope.row.status === '待处理'">

              <template v-if="scope.row.userDecision === 'pending_review'">
                <div style="display: flex; gap: 4px; justify-content: center;">
                  <button class="custom-btn action-btn bg-success" @click="handleAdminApproval(scope.row, 'approve')">✅ 同意访问</button>
                  <button class="custom-btn action-btn bg-danger" @click="handleAdminApproval(scope.row, 'reject')">❌ 拒绝访问</button>
                </div>
              </template>

              <template v-else-if="scope.row.level === '高风险'">
                <button v-if="scope.row.action !== '阻断隔离'" class="custom-btn action-btn bg-danger" @click="processAlert(scope.row, '阻断隔离')">阻断隔离</button>
                <el-tag v-else type="danger" size="small" style="margin-right: 5px;">已阻断</el-tag>
                
                <button class="custom-btn action-btn bg-danger" @click="processAlert(scope.row, '发起调查')">发起调查</button>
              </template>
              <template v-else-if="scope.row.level === '中风险'">
                <button class="custom-btn action-btn bg-warning" @click="processAlert(scope.row, '发送预警')">发送预警</button>
                <button class="custom-btn action-btn bg-warning" @click="processAlert(scope.row, '限制权限')">限制权限</button>
              </template>
              <template v-else>
                <button class="custom-btn action-btn bg-success" @click="processAlert(scope.row, '发送提醒')">发送提醒</button>
                <button class="custom-btn action-btn bg-success" @click="processAlert(scope.row, '自动校准')">自动校准</button>
              </template>
              <button class="custom-btn action-btn" @click="openFalsePositiveDialog(scope.row)" style="margin-top: 4px; background-image: linear-gradient(30deg, #ff6b6b, #ee5a6f);">标记误报</button>
            </template>
            <!-- 【优化】已完结时显示具体操作类型 -->
            <div v-else style="display: flex; flex-direction: column; gap: 4px; align-items: center;">
              <!-- 1. 已阻断 -->
              <div v-if="scope.row.action === '阻断隔离'" style="display: flex; flex-direction: column; gap: 8px; align-items: center;">
                <el-tag type="danger" effect="dark" size="default">
                  🚫 已阻断隔离
                </el-tag>
                <button class="custom-btn action-btn bg-success" @click="handleUnblock(scope.row)" style="font-size: 12px; padding: 4px 12px;">
                  🔓 解除阻断
                </button>
              </div>
              
              <!-- 2. 标记误报 -->
              <el-tag v-if="scope.row.is_false_positive || scope.row.userDecision === 'false_positive'" type="success" effect="dark" size="default">
                ✅ 已标记误报
              </el-tag>
              
              <!-- 3. 用户决策 -->
              <el-tag v-if="scope.row.userDecision === 'user_confirmed'" type="success" size="default">
                👤 用户已确认
              </el-tag>
              <el-tag v-else-if="scope.row.userDecision === 'user_cancelled'" type="info" size="default">
                👤 用户已取消
              </el-tag>
              <el-tag v-else-if="scope.row.userDecision === 'pending_review'" type="warning" size="default">
                👤 已上报审批
              </el-tag>
              
              <!-- 4. 已发起调查 -->
              <el-tag v-if="scope.row.userDecision === 'investigated'" type="warning" effect="dark" size="default">
                🔍 已发起调查
              </el-tag>
              
              <!-- 5. 默认已完结（其他情况） -->
              <span v-if="!scope.row.action && !scope.row.is_false_positive && !scope.row.userDecision" style="color: #909399; font-size: 14px;">
                已完结
              </span>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 20px; display: flex; justify-content: flex-end;">
        <el-pagination background layout="total, prev, pager, next" :total="totalCount" v-model:current-page="currentPage" :page-size="pageSize" @current-change="handleCurrentChange" />
      </div>
    </el-card>

    <!-- 【新增】误判反馈对话框 -->
    <el-dialog v-model="falsePositiveDialogVisible" title="标记误报 - 基线修正反馈" width="500px">
      <div style="padding: 10px; font-size: 16px;">
        <el-alert
          title="误判反馈说明"
          type="info"
          :closable="false"
          style="margin-bottom: 20px;"
        >
          <p style="margin: 5px 0; font-size: 14px;">
            标记为误报后，系统将：<br>
            1. 记录该样本用于模型训练<br>
            2. 自动修正该用户的行为基线<br>
            3. 降低类似行为的异常判定阈值
          </p>
        </el-alert>

        <el-form label-width="100px" style="font-size: 16px;">
          <el-form-item label="告警编号">
            <span style="color: #606266; font-size: 15px;">{{ currentAlert?.alertId }}</span>
          </el-form-item>
          <el-form-item label="用户">
            <span style="color: #606266; font-size: 15px;">{{ currentAlert?.user }}</span>
          </el-form-item>
          <el-form-item label="误判原因" required>
            <el-input
              v-model="feedbackReason"
              type="textarea"
              :rows="4"
              placeholder="请说明为什么这是误判（例如：员工出差、正常业务操作等）"
              maxlength="500"
              show-word-limit
              style="font-size: 15px;"
            />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="falsePositiveDialogVisible = false" style="font-size: 14px;">取消</el-button>
          <el-button type="primary" @click="submitFalsePositiveFeedback" :disabled="!feedbackReason.trim()" style="font-size: 14px;">
            确认误判并修正基线
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Search, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs' // 建议引入 dayjs 格式化时间，确保显示友好

const filterRisk = ref('')
const filterStatus = ref('')
const searchKeyword = ref('')
const selectedRows = ref([])

const currentPage = ref(1)
const pageSize = ref(10)

// 从后端获取真实数据
const alertList = ref([])

// 获取告警数据
const fetchAlerts = async () => {
  try {
    const token = localStorage.getItem('sys_token')

    if (!token) {
      console.error('未找到 Token，请先登录')
      alertList.value = []
      return
    }

    // 第一步：先获取数据总数
    const firstRes = await axios.get('http://127.0.0.1:5000/api/alerts', {
      params: {
        page: 1,
        per_page: 1  // 只请求 1 条数据，用于获取 total
      },
      headers: {
        Authorization: `Bearer ${token}`
      }
    })

    console.log('API Response:', firstRes.data)

    if (firstRes.data && firstRes.data.code === 200 && firstRes.data.data) {
      const total = firstRes.data.data.total || 0
      console.log('数据库告警总数:', total)

      // 第二步：根据实际总数请求所有数据
      if (total > 0) {
        const res = await axios.get('http://127.0.0.1:5000/api/alerts', {
          params: {
            page: 1,
            per_page: total  // 动态设置：请求所有数据
          },
          headers: {
            Authorization: `Bearer ${token}`
          }
        })

        if (res.data && res.data.code === 200 && res.data.data) {
          const alertsData = res.data.data.alerts || []
          console.log('实际获取告警数据数量:', alertsData.length)

          // 转换为前端期望的格式（重点修复时间映射）
          alertList.value = alertsData.map(alert => ({
            alertId: `AL-${alert.id}`,
            // 修复：确保数据库timestamp字段正确赋值给time，并格式化显示
            time: alert.timestamp ? dayjs(alert.timestamp).format('YYYY-MM-DD HH:mm:ss') : '',
            level: alert.alert_level === 'high' || alert.alert_level === 'critical' ? '高风险' : 
                   alert.alert_level === 'medium' ? '中风险' : '低风险',
            type: alert.description || alert.behavior_type || '',
            rule: alert.action_detail || '',
            user: alert.user_name || 'Unknown',
            // 【修复】状态映射：pending_review和pending都显示为待处理
            status: (alert.feedback_type === 'pending' || alert.feedback_type === 'pending_review') ? '待处理' : '已处置',
            networkType: alert.network_type || '',
            locationHint: alert.location_hint || '',
            discountFactor: 1.0,
            action: alert.action_taken === 'block' ? '阻断隔离' : '',
            id: alert.id,
            is_false_positive: alert.is_false_positive || false,
            // 【新增】用户决策状态
            userDecision: alert.feedback_type || '',
            // 【新增】执行状态
            executionStatus: alert.execution_status || 'pending'
          }))
        }
      } else {
        alertList.value = []
      }
    }
  } catch (error) {
    console.error('获取告警数据失败:', error)
    alertList.value = []
  }
}

// 组件挂载时获取数据
onMounted(() => {
  fetchAlerts()
})

const filteredData = computed(() => {
  return alertList.value.filter(item => {
    const matchRisk = filterRisk.value === '' || item.level === filterRisk.value
    const matchStatus = filterStatus.value === '' || item.status === filterStatus.value
    const matchKeyword = item.alertId.includes(searchKeyword.value) || item.user.includes(searchKeyword.value)
    return matchRisk && matchStatus && matchKeyword
  })
})

const totalCount = computed(() => filteredData.value.length)

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredData.value.slice(start, end)
})

const handleCurrentChange = (val) => {
  currentPage.value = val
}

const handleSelectionChange = (val) => {
  selectedRows.value = val
}

const handleFilter = () => {
}

// 【新增】刷新数据功能
const refreshData = async () => {
  ElMessage.info('正在刷新数据...')
  await fetchAlerts()
  ElMessage.success('数据已更新')
}

// 【新增】网络环境标签映射
const getNetworkTypeTag = (type) => {
  const map = {
    'office': 'success',
    'home': 'info',
    'mobile': 'warning',
    'vpn': 'danger'
  }
  return map[type] || 'info'
}

const getNetworkTypeText = (type) => {
  const map = {
    'office': '公司',
    'home': '家庭',
    'mobile': '移动',
    'vpn': 'VPN'
  }
  return map[type] || '未知'
}

const processAlert = async (row, action) => {
  if (action === '阻断隔离') {
    ElMessageBox.confirm(`确认对 ${row.user} 采取账号封禁措施吗？\n\n阻断后该用户将无法登录系统。`, '高危操作确认', {
      confirmButtonText: '立即阻断',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(async () => {
      try {
        const token = localStorage.getItem('sys_token')
        const response = await fetch(`http://127.0.0.1:5000/api/alerts/${row.id}/execute-block`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          }
        })
        
        const result = await response.json()
        if (result.code === 200) {
          ElMessage.success(result.message || '阻断成功！')
          row.status = '已处置'
          row.action = '阻断隔离'
          
          // 刷新列表
          setTimeout(() => {
            fetchAlerts()
          }, 1000)
        } else {
          ElMessage.error(result.message || '阻断指令下发失败')
        }
      } catch (error) {
        console.error('阻断操作失败:', error)
        ElMessage.error('网络错误，请稍后重试')
      }
    }).catch(() => {})
  } else if (action === '发起调查') {
    row.status = '已处置' 
    ElMessage.success('已发起调查流程，强制核查。')
  } else if (action === '发送预警') {
    ElMessage.success(`已向 ${row.user} 发送预警通知，重点监控。`)
    row.status = '已处置'
  } else if (action === '限制权限') {
    ElMessage.success(`已限制 ${row.user} 的敏感操作权限。`)
    row.status = '已处置'
  } else if (action === '发送提醒') {
    ElMessage.success(`温和提醒已发送给 ${row.user}，并记录日志。`)
    row.status = '已处置'
  } else if (action === '自动校准') {
    ElMessage.success(`针对 ${row.user} 的行为基线已完成自动校准。`)
    row.status = '已处置'
  } else if (action === '标记误报') {
    row.status = '已处置'
    ElMessage.info('已将该告警标记为误报，系统将自动修正行为基线。')
  }
}

// 【新增】处理管理员对"上报请求"的审批操作
const handleAdminApproval = async (row, actionType) => {
  const token = localStorage.getItem('sys_token')
  if (!token) return

  try {
    if (actionType === 'approve') {
      // 1. 同意访问：调用误报接口（自动给用户补偿 +10 信任分，并解除终端黑屏）
      ElMessageBox.confirm(`确认同意 ${row.user} 的访问申请？系统将为其解除终端黑屏并恢复信任分。`, '同意审批', {
        confirmButtonText: '确定同意',
        cancelButtonText: '取消',
        type: 'success',
      }).then(async () => {
        const response = await fetch(`http://127.0.0.1:5000/api/alerts/${row.id}/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({ feedback_type: 'false_positive', feedback_reason: '管理员同意访问申请' })
        })
        const result = await response.json()
        if (result.code === 200) {
          ElMessage.success('已同意访问！终端黑屏将自动解除，信任分已返还。')
          row.status = '已处置'
          row.is_false_positive = true
          row.userDecision = 'false_positive' // 触发终端轮询解除
        }
      }).catch(() => {})
      
    } else if (actionType === 'reject') {
      // 2. 拒绝访问：调用状态更新接口，维持终端黑屏状态
      ElMessageBox.confirm(`确认拒绝 ${row.user} 的访问申请？终端将继续保持黑屏锁定。`, '拒绝审批', {
        confirmButtonText: '强制拒绝',
        cancelButtonText: '取消',
        type: 'error',
      }).then(async () => {
        const response = await fetch(`http://127.0.0.1:5000/api/alerts/${row.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({ action: 'block' }) // 发送 block 指令
        })
        const result = await response.json()
        if (result.code === 200) {
          ElMessage.warning('已拒绝申请！终端将持续物理隔离。')
          row.status = '已处置'
          row.userDecision = 'rejected' // 触发终端提示
        }
      }).catch(() => {})
    }
  } catch (error) {
    console.error('审批操作失败:', error)
    ElMessage.error('网络错误，请稍后重试')
  }
}

// 【新增】解除用户阻断
const handleUnblock = async (row) => {
  // 从告警中获取user_id
  const alertData = alertList.value.find(a => a.id === row.id)
  if (!alertData || !alertData.user_id) {
    ElMessage.error('无法找到用户信息')
    return
  }
  
  ElMessageBox.confirm(
    `确认解除 ${row.user} 的账号阻断吗？\n\n解除后该用户可以正常登录系统。`,
    '解除阻断确认',
    {
      confirmButtonText: '确认解除',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    try {
      const token = localStorage.getItem('sys_token')
      const response = await fetch(`http://127.0.0.1:5000/api/users/${alertData.user_id}/unblock`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      })
      const result = await response.json()
      if (result.code === 200) {
        ElMessage.success(result.message)
        fetchAlerts() // 刷新列表
      } else {
        ElMessage.error(result.message || '解除阻断失败')
      }
    } catch (error) {
      console.error('解除阻断失败:', error)
      ElMessage.error('网络错误，请稍后重试')
    }
  }).catch(() => {})
}

// 【新增】误判反馈对话框
const falsePositiveDialogVisible = ref(false)
const currentAlert = ref(null)
const feedbackReason = ref('')

const openFalsePositiveDialog = (row) => {
  currentAlert.value = row
  feedbackReason.value = ''
  falsePositiveDialogVisible.value = true
}

const submitFalsePositiveFeedback = async () => {
  if (!feedbackReason.value.trim()) {
    ElMessage.warning('请填写误判原因')
    return
  }
  
  try {
    // 调用后端API
    const token = localStorage.getItem('sys_token')
    const response = await fetch(`http://127.0.0.1:5000/api/alerts/${currentAlert.value.id}/feedback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        feedback_type: 'false_positive',
        feedback_reason: feedbackReason.value
      })
    })
    
    const result = await response.json()
    
    if (result.code === 200) {
      ElMessage.success('误判反馈提交成功，基线已自动修正')
      currentAlert.value.status = '已处置'
      currentAlert.value.is_false_positive = true
      falsePositiveDialogVisible.value = false
      
      // 如果后端返回已修正基线，显示提示
      if (result.data.baseline_corrected) {
        ElMessage.info('系统已根据误判样本自动修正行为基线')
      }
    } else {
      ElMessage.error(result.message || '反馈提交失败')
    }
  } catch (error) {
    console.error('提交误判反馈失败:', error)
    ElMessage.error('网络错误，请稍后重试')
  }
}

// 【新增】批量标记误报
const handleBatchProcess = () => {
  ElMessageBox.confirm(
    `确认将 ${selectedRows.value.length} 条告警标记为误报吗？这将触发基线自动修正。`,
    '批量误判确认',
    {
      confirmButtonText: '确认',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    const token = localStorage.getItem('sys_token')
    let successCount = 0
    for (const row of selectedRows.value) {
      try {
        const response = await fetch(`http://127.0.0.1:5000/api/alerts/${row.id}/feedback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            feedback_type: 'false_positive',
            feedback_reason: '批量标记为误报'
          })
        })
        
        const result = await response.json()
        if (result.code === 200) {
          row.status = '已处置'
          row.is_false_positive = true
          successCount++
        }
      } catch (error) {
        console.error('批量标记失败:', error)
      }
    }
    
    ElMessage.success(`成功标记 ${successCount} 条告警为误报，基线已自动修正`)
    selectedRows.value = []
  }).catch(() => {})
}
</script>

<style scoped>
.custom-btn {
  border: none;
  color: #fff;
  background-image: linear-gradient(30deg, #0400ff, #4ce3f7);
  border-radius: 20px;
  background-size: 100% auto;
  font-family: inherit;
  font-size: 14px;
  padding: 0.4em 1em;
  height: 32px;
  line-height: normal;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
}

.custom-btn:hover {
  background-position: right center;
  background-size: 200% auto;
  -webkit-animation: pulse 2s infinite;
  animation: pulse512 1.5s infinite;
}

.action-btn {
  font-size: 12px;
  padding: 0.25em 0.8em;
  height: 26px;
  margin: 2px;
}

.bg-danger {
  background-image: linear-gradient(30deg, #ff4b2b, #ff416c);
}

.bg-warning {
  background-image: linear-gradient(30deg, #f12711, #f5af19);
}

.bg-success {
  background-image: linear-gradient(30deg, #11998e, #38ef7d);
}

@keyframes pulse512 {
  0% { box-shadow: 0 0 0 0 #05bada66; }
  70% { box-shadow: 0 0 0 10px rgb(0 0 0 / 0%); }
  100% { box-shadow: 0 0 0 0 rgb(0 0 0 / 0%); }
}
</style>