<template>
  <div style="padding: 20px">
    <!-- 合规概览统计卡片 -->
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center">
            <div style="font-size: 14px; color: #909399; margin-bottom: 10px">终端总数</div>
            <div style="font-size: 32px; font-weight: bold; color: #409EFF">{{ stats.total_devices }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center">
            <div style="font-size: 14px; color: #909399; margin-bottom: 10px">合规设备</div>
            <div style="font-size: 32px; font-weight: bold; color: #67C23A">{{ stats.compliant_devices }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center">
            <div style="font-size: 14px; color: #909399; margin-bottom: 10px">警告设备</div>
            <div style="font-size: 32px; font-weight: bold; color: #E6A23C">{{ stats.warning_devices }}</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="text-align: center">
            <div style="font-size: 14px; color: #909399; margin-bottom: 10px">不合规设备</div>
            <div style="font-size: 32px; font-weight: bold; color: #F56C6C">{{ stats.non_compliant_devices }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 合规率仪表盘 + 趋势图 -->
    <el-row :gutter="20" style="margin-bottom: 20px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div style="font-size: 16px; font-weight: bold">整体合规率</div>
          </template>
          <div style="text-align: center; padding: 20px">
            <el-progress
              type="dashboard"
              :percentage="stats.compliance_rate"
              :color="progressColors"
              style="width: 250px"
            >
              <template #default="{ percentage }">
                <span style="font-size: 36px; font-weight: bold">{{ percentage }}%</span>
              </template>
            </el-progress>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div style="font-size: 16px; font-weight: bold">合规趋势（近7天）</div>
              <el-button type="primary" size="small" @click="refreshComplianceData" :loading="loading">
                <el-icon><Refresh /></el-icon> 刷新数据
              </el-button>
            </div>
          </template>
          <div ref="trendChartRef" style="height: 250px; width: 100%"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 设备列表 -->
    <el-card shadow="never">
      <template #header>
        <div class="header-title">
          <span style="font-size: 16px; font-weight: bold;">终端资产准入与管控</span>
        </div>
      </template>

      <div style="margin-bottom: 20px; display: flex; gap: 10px;">
        <el-select v-model="filterStatus" placeholder="状态过滤" style="width: 140px;" @change="handleFilterChange">
          <el-option label="所有状态" value="" />
          <el-option label="合规设备" value="compliant" />
          <el-option label="警告设备" value="warning" />
          <el-option label="不合规设备" value="non_compliant" />
        </el-select>
        <el-input v-model="searchKeyword" placeholder="搜索MAC地址或使用人..." style="width: 250px;">
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button type="primary" @click="handleSearch">
          <el-icon><Search /></el-icon> 查询设备
        </el-button>
      </div>

      <el-table :data="paginatedData" style="width: 100%" border v-loading="loading">
        <el-table-column prop="macAddress" label="MAC 地址" width="170" />
        <el-table-column prop="os" label="操作系统" width="140" />
        <el-table-column prop="user" label="当前使用人" width="120" />
        <el-table-column prop="patchStatus" label="补丁状态" width="120" align="center">
          <template #default="scope">
            <el-tag :type="getPatchStatusType(scope.row.patchStatus)" size="small">
              {{ scope.row.patchStatus }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="antivirusStatus" label="杀毒软件" width="180" align="center">
          <template #default="scope">
            <el-tag :type="getAVStatusType(scope.row.antivirusStatus)" size="small">
              {{ scope.row.antivirusStatus }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="complianceStatus" label="合规状态" width="120" align="center">
          <template #default="scope">
            <el-tag :type="getComplianceType(scope.row.complianceStatus)" effect="dark" size="small">
              {{ getComplianceText(scope.row.complianceStatus) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="lastHealthCheck" label="最后健康检查" width="180" />
        <el-table-column label="合规控制" align="center" width="150">
          <template #default="scope">
            <el-switch
              v-model="scope.row.allowed"
              inline-prompt
              active-text="允许接入"
              inactive-text="网络隔离"
              active-color="#13ce66"
              inactive-color="#ff4949"
              @change="(val) => handleControlChange(scope.row, val)"
            />
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 20px; display: flex; justify-content: flex-end;">
        <el-pagination background layout="total, prev, pager, next" :total="totalCount" v-model:current-page="currentPage" :page-size="pageSize" @current-change="handleCurrentChange" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Search, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import * as echarts from 'echarts'

const filterStatus = ref('')
const searchKeyword = ref('')

const currentPage = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const totalCount = ref(0)
const trendChartRef = ref(null)

// 合规统计数据
const stats = ref({
  total_devices: 0,
  compliant_devices: 0,
  warning_devices: 0,
  non_compliant_devices: 0,
  compliance_rate: 0
})

// 进度条颜色
const progressColors = [
  { color: '#F56C6C', percentage: 60 },
  { color: '#E6A23C', percentage: 80 },
  { color: '#67C23A', percentage: 100 }
]

// 从后端加载设备数据
const deviceList = ref([])

const loadDevices = async () => {
  loading.value = true
  try {
    const token = localStorage.getItem('sys_token')
    
    // 构建查询参数
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    
    // 添加状态过滤
    if (filterStatus.value) {
      params.compliance_status = filterStatus.value
    }
    
    // 添加关键词搜索
    if (searchKeyword.value) {
      params.keyword = searchKeyword.value
    }
    
    // 并行加载设备列表和统计数据
    const [devicesResponse, statsResponse] = await Promise.all([
      axios.get('/api/health/devices', {
        headers: { 'Authorization': `Bearer ${token}` },
        params
      }),
      axios.get('/api/health/stats', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
    ])
    
    if (devicesResponse.data.code === 200) {
      const data = devicesResponse.data.data
      totalCount.value = data.total
      
      // 转换数据格式适配前端
      deviceList.value = data.devices.map(device => ({
        macAddress: device.mac_address || '未知',
        os: device.os_info || '未知',
        user: device.user_name || '未知',
        patchStatus: device.patch_status,
        antivirusStatus: device.antivirus_status,
        complianceStatus: device.compliance_status,
        lastHealthCheck: device.last_health_check,
        allowed: device.compliance_status !== 'non_compliant'
      }))
    }
    
    // 更新统计数据
    if (statsResponse.data.code === 200) {
      const statsData = statsResponse.data.data
      stats.value = {
        total_devices: statsData.total_devices,
        compliant_devices: statsData.compliant_devices,
        warning_devices: statsData.warning_devices,
        non_compliant_devices: statsData.non_compliant_devices,
        compliance_rate: statsData.compliance_rate
      }
      
      // 绘制趋势图
      drawTrendChart()
    }
  } catch (error) {
    console.error('加载设备列表失败:', error)
    ElMessage.error('加载设备列表失败')
  } finally {
    loading.value = false
  }
}

// 绘制合规趋势图
const drawTrendChart = async () => {
  if (!trendChartRef.value) return
  
  const chart = echarts.init(trendChartRef.value)
  
  try {
    const token = localStorage.getItem('sys_token')
    
    // 从后端获取真实的近7天合规率数据
    const response = await axios.get('/api/health/compliance-history', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    
    let dates = []
    let rates = []
    
    if (response.data.code === 200 && response.data.data) {
      dates = response.data.data.dates
      rates = response.data.data.compliance_rates
    } else {
      // 如果接口失败，显示空数据
      ElMessage.warning('无法获取合规历史数据')
    }
    
    const option = {
      tooltip: {
        trigger: 'axis',
        formatter: '{b}<br/>合规率: {c}%'
      },
      xAxis: {
        type: 'category',
        data: dates,
        boundaryGap: false
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        axisLabel: {
          formatter: '{value}%'
        }
      },
      series: [
        {
          data: rates,
          type: 'line',
          smooth: true,
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(64, 158, 255, 0.3)' },
              { offset: 1, color: 'rgba(64, 158, 255, 0.05)' }
            ])
          },
          lineStyle: {
            color: '#409EFF',
            width: 3
          },
          itemStyle: {
            color: '#409EFF'
          }
        }
      ],
      grid: {
        left: '3%',
        right: '4%',
        bottom: '3%',
        containLabel: true
      }
    }
    
    chart.setOption(option)
    
    // 响应式调整
    window.addEventListener('resize', () => chart.resize())
  } catch (error) {
    console.error('获取合规历史数据失败:', error)
    ElMessage.error('获取合规历史数据失败')
  }
}

// 筛选后的数据（后端已过滤，这里直接使用）
const filteredData = computed(() => deviceList.value)

const paginatedData = computed(() => deviceList.value)

const handleCurrentChange = (val) => {
  currentPage.value = val
  loadDevices()
}

const handleSearch = () => {
  currentPage.value = 1
  loadDevices()
}

// 处理状态筛选变化
const handleFilterChange = () => {
  currentPage.value = 1
  loadDevices()
}

const handleControlChange = async (row, isAllowed) => {
  try {
    const token = localStorage.getItem('sys_token')
    // TODO: 调用后端API更新设备状态
    // await axios.put(`/api/health/devices/${row.deviceId}/control`, { allowed: isAllowed })
    
    if (isAllowed) {
      ElMessage.success(`设备 ${row.macAddress} 已解除隔离，允许接入网络。`)
    } else {
      ElMessage.warning(`设备 ${row.macAddress} 已被强制断网隔离！`)
    }
  } catch (error) {
    ElMessage.error('操作失败')
    // 恢复原状态
    row.allowed = !isAllowed
  }
}

// 状态标签类型映射
const getPatchStatusType = (status) => {
  const map = {
    '已更新': 'success',
    '缺失关键补丁': 'warning',
    '严重落后': 'danger'
  }
  return map[status] || 'info'
}

const getAVStatusType = (status) => {
  if (status.includes('正常')) return 'success'
  if (status.includes('过期')) return 'warning'
  if (status.includes('未安装') || status.includes('未运行')) return 'danger'
  return 'info'
}

const getComplianceType = (status) => {
  const map = {
    'compliant': 'success',
    'warning': 'warning',
    'non_compliant': 'danger'
  }
  return map[status] || 'info'
}

const getComplianceText = (status) => {
  const map = {
    'compliant': '合规',
    'warning': '警告',
    'non_compliant': '不合规'
  }
  return map[status] || status
}

// 刷新合规数据
const refreshComplianceData = async () => {
  await loadDevices()
  ElMessage.success('数据已刷新')
}

// 页面加载时获取数据
onMounted(() => {
  loadDevices()
})
</script>

<style scoped>
</style>