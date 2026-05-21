<template>
  <div style="padding: 20px">
    <el-card shadow="never">
      <template #header>
        <div class="flex-between">
          <span style="font-size: 16px; font-weight: bold;">全链路操作审记</span>
          <el-button type="primary" text><el-icon><Download /></el-icon> 导出报表</el-button>
        </div>
      </template>

      <div style="margin-bottom: 20px; display: flex; gap: 10px; justify-content: space-between; flex-wrap: wrap;">
        <div style="display: flex; gap: 10px; align-items: center;">
          <span style="font-weight: bold; color: #606266;">数据分类：</span>
          <el-radio-group v-model="systemFilter" @change="handleSystemFilterChange" size="default">
            <el-radio-button label="all">全部数据</el-radio-button>
            <el-radio-button label="oa_access">协同审批/财务报销</el-radio-button>
            <el-radio-button label="system">内部源码仓库</el-radio-button>
            <el-radio-button label="auth">登录认证</el-radio-button>
            <el-radio-button label="behavior">行为监控</el-radio-button>
            <el-radio-button label="device">设备管理</el-radio-button>
          </el-radio-group>
        </div>
      </div>

      <div style="margin-bottom: 20px; display: flex; gap: 10px; justify-content: space-between;">
        <div style="display: flex; gap: 10px;">
          <el-input v-model="searchKeyword" placeholder="搜索操作人员、文件名、IP地址..." style="width: 300px;">
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" @click="handleSearch">检索 日志</el-button>
        </div>
        <!-- 【新增】刷新按钮 -->
        <el-button type="success" @click="handleRefresh">
          <el-icon><Refresh /></el-icon> 刷新数据
        </el-button>
      </div>

      <el-table :data="paginatedData" style="width: 100%" border v-loading="loading">
        <el-table-column prop="time" label="操作时间" width="180" />
        <el-table-column prop="user" label="操作人员" width="160" />
        <el-table-column prop="action" label="操作类型" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.type" effect="plain">{{ scope.row.action }}</el-tag>
          </template>
        </el-table-column>
        
        <!-- 【删除】原有的四个独立列 -->
        
        <el-table-column prop="target" label="所属模块" width="180" />
        <el-table-column label="操作详情" min-width="250">
          <template #default="scope">
            <div class="log-detail-box">
              <div class="detail-main">{{ scope.row.detail }}</div>
              <!-- 【新增】行为监控专用字段详情展示 -->
              <div v-if="scope.row.fileOperation && Object.keys(scope.row.fileOperation).length > 0" class="detail-item">
                <el-tag size="small" type="info">📁 文件操作</el-tag> 
                <span v-if="scope.row.fileOperation.has_usb_file_op" style="color: #e6a23c; font-weight: bold;">U盘操作</span>
                <span v-if="scope.row.fileOperation.has_sensitive_file_op" style="color: #f56c6c; margin-left: 5px;">敏感文件</span>
                <span v-if="!scope.row.fileOperation.has_usb_file_op && !scope.row.fileOperation.has_sensitive_file_op">{{ scope.row.fileOperation.operation_detail || '无' }}</span>
              </div>
              <div v-if="scope.row.emailOperation && scope.row.emailOperation.is_sending_email" class="detail-item">
                <el-tag size="small" type="danger">📧 邮件附件</el-tag> 
                <span>检测到发送行为</span>
              </div>
              <div v-if="scope.row.browserOperation && scope.row.browserOperation.is_browser_active" class="detail-item">
                <el-tag size="small" type="info"> 浏览器</el-tag> 
                <span>{{ scope.row.browserOperation.browser_name }} - {{ scope.row.browserOperation.active_tab_title }}</span>
              </div>
              <div v-if="scope.row.isScreenSharing" class="detail-item">
                <el-tag size="small" type="warning">🖥️ 屏幕共享</el-tag> 
                <span style="color: #e6a23c;">{{ scope.row.screenShareApp }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="客户端IP" width="140" />
        <el-table-column prop="ip" label="客户端IP" width="140" />
        <el-table-column prop="networkType" label="网络环境" width="100" align="center">
          <template #default="scope">
            <el-tag :type="getNetworkTypeTag(scope.row.networkType)" size="small">
              {{ getNetworkTypeText(scope.row.networkType) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="locationHint" label="接入位置" width="140" />
        <!-- 【新增】操作列 - 根据文档要求，所有全链路日志都应支持上报 -->
        <el-table-column label="操作" width="80" align="center" fixed="right">
          <template #default="scope">
            <el-button 
              class="report-btn"
              type="warning" 
              size="small" 
              @click="handleReport(scope.row)"
              :disabled="scope.row.hasAlert"
            >
              上报
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 20px; display: flex; justify-content: flex-end;">
        <el-pagination background layout="prev, pager, next, total" :total="totalCount" v-model:current-page="currentPage" :page-size="pageSize" @current-change="handleCurrentChange" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Search, Download, Refresh, Warning } from '@element-plus/icons-vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const totalCount = ref(0)
const tableData = ref([])
const loading = ref(false)
const systemFilter = ref('all')  // 系统分类筛选
const reportDialogVisible = ref(false)
const currentReportLog = ref(null)
const reportReason = ref('')

// 【新增】获取日志数据
const fetchLogs = async (page = 1) => {
  loading.value = true
  try {
    const params = {
      page: page,
      per_page: pageSize.value,
    }
    
    // 如果选择了特定系统，传递 log_type 参数
    if (systemFilter.value !== 'all') {
      params.log_type = systemFilter.value
    }
    
    // 【新增】传递搜索关键字到后端
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    
    const res = await axios.get('http://127.0.0.1:5000/api/audit/logs', { params })
    
    if (res.data.code === 200) {
      const backendLogs = res.data.data.logs
      totalCount.value = res.data.data.total
      
      // 字段映射：后端 -> 前端
      tableData.value = backendLogs.map(log => {
        // 根据 IP 简单推断网络类型
        const ip = log.ip_address || 'Unknown'
        let networkType = log.network_type || 'office'
        let locationHint = log.location_hint || '公司网络'
        
        if (ip.includes('10.')) {
          networkType = networkType === 'unknown' ? 'vpn' : networkType
          locationHint = locationHint === '未知位置' ? 'VPN 连接' : locationHint
        } else if (!ip.startsWith('192.168.')) {
          networkType = networkType === 'unknown' ? 'mobile' : networkType
          locationHint = locationHint === '未知位置' ? '移动网络/异地' : locationHint
        }
        
        return {
          id: log.id,  // 【新增】添加日志ID，用于上报功能
          time: log.created_at,
          user: log.user_name || 'System',
          action: log.action,
          type: log.status === 'success' ? 'success' : (log.status === 'warning' ? 'warning' : 'danger'),
          target: log.module || 'System',
          detail: log.description,
          ip: ip,
          networkType: networkType,
          locationHint: locationHint,
          log_type: log.log_type,
          hasAlert: false,  // 标记是否已上报
          // 【新增】行为监控专用字段
          fileOperation: log.file_operation,
          emailOperation: log.email_operation,
          browserOperation: log.browser_operation,
          isScreenSharing: log.is_screen_sharing,
          screenShareApp: log.screen_share_app
        }
      })
    }
  } catch (err) {
    console.error('获取日志失败:', err)
    ElMessage.error('获取日志数据失败')
  } finally {
    loading.value = false
  }
}

// 【修改】移除前端过滤逻辑，改为直接使用后端返回的数据
const paginatedData = computed(() => {
  return tableData.value
})

const handleCurrentChange = (val) => {
  currentPage.value = val
  fetchLogs(val)
}

const handleSearch = () => {
  currentPage.value = 1
  fetchLogs(1)
}

const handleSystemFilterChange = () => {
  currentPage.value = 1
  fetchLogs(1)
  ElMessage.success(`已筛选：${systemFilter.value === 'all' ? '全部系统' : getSystemName(systemFilter.value)}`)
}

const handleRefresh = () => {
  fetchLogs(currentPage.value)
  ElMessage.success('数据已刷新')
}

// 【新增】处理日志上报
const handleReport = async (row) => {
  try {
    // 弹出对话框确认上报原因
    await ElMessageBox.prompt('请输入上报原因（选填）', '上报可疑行为', {
      confirmButtonText: '确认上报',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：疑似未授权访问、异常数据传输等',
      type: 'warning',
      icon: Warning
    }).then(async ({ value }) => {
      loading.value = true
      const reason = value || '管理员人工上报'
      
      // 调用后端上报接口
      const res = await axios.post(
        `http://127.0.0.1:5000/api/audit/logs/${row.id}/report`,
        { report_reason: reason },
        {
          headers: {
            'Authorization': 'Bearer ' + localStorage.getItem('sys_token')
          }
        }
      )
      
      if (res.data.code === 200) {
        ElMessage.success(res.data.message)
        // 标记该行已上报
        row.hasAlert = true
        // 刷新列表
        fetchLogs(currentPage.value)
      } else {
        ElMessage.error(res.data.message || '上报失败')
      }
    })
  } catch (err) {
    // 用户取消操作
    if (err !== 'cancel') {
      console.error('上报失败:', err)
      ElMessage.error('上报失败，请稍后重试')
    }
  } finally {
    loading.value = false
  }
}

// 系统名称映射
const getSystemName = (type) => {
  const map = {
    'oa_access': 'OA业务操作',
    'system': '系统级操作',
    'auth': '登录认证',
    'behavior': '行为监控',
    'device': '设备管理'
  }
  return map[type] || type
}

onMounted(() => {
  fetchLogs(1)
})

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
</script>
 
<style scoped>
 .flex-between {
   display: flex;
   justify-content: space-between;
   align-items: center;
 }
 
 /* 上报按钮样式优化 */
 .report-btn {
   padding: 2px 6px !important;
   font-size: 11px !important;
   height: 22px !important;
   line-height: 16px !important;
   min-width: 40px !important;
 }

 /* 操作详情样式优化 */
 .log-detail-box {
   line-height: 1.6;
 }
 .detail-main {
   margin-bottom: 6px;
   word-break: break-all;
 }
 .detail-item {
   margin-top: 4px;
   font-size: 12px;
   color: #606266;
   background-color: #f8f9fb;
   padding: 2px 6px;
   border-radius: 4px;
   display: inline-block;
   margin-right: 6px;
 }
</style>