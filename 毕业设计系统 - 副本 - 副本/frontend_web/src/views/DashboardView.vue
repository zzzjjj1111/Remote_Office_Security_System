<template>
  <div class="dashboard-wrapper">
    <el-row :gutter="20">
      <el-col :span="6">
        <div class="card">
          <div class="card-title">当前防护终端数</div>
          <div class="small-desc text-primary">{{ stats.total_devices }}</div>   
          <div class="go-corner">
            <div class="go-arrow"></div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="card">
          <div class="card-title">异常行为检测数</div>
          <div class="small-desc text-danger">{{ stats.high_risk_events }}</div>
          <div class="go-corner">
            <div class="go-arrow"></div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="card">
          <div class="card-title">敏感操作拦截数</div>
          <div class="small-desc text-warning">{{ stats.blocked_events }}</div>      
          <div class="go-corner">
            <div class="go-arrow"></div>
          </div>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="card">
          <div class="card-title">终端行为合规率</div>
          <div class="small-desc text-success">{{ stats.compliance_rate }}</div> 
          <div class="go-corner">
            <div class="go-arrow"></div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px;">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span style="font-size: 18px; font-weight: bold;">动态信任基线波动</span>
              <el-select v-model="selectedDay" size="default" style="width: 140px" @change="updateChartData">
                <el-option 
                  v-for="option in dateOptions" 
                  :key="option.value" 
                  :label="option.label" 
                  :value="option.value"
                ></el-option>
              </el-select>
            </div>
          </template>
          <div ref="chartRef" style="height: 350px; width: 100%;"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" header="多维感知分析日志">
          <div style="padding: 5px 0; max-height: 350px; overflow-y: auto;">
            <el-timeline v-if="logs.length > 0" class="custom-timeline">
              <el-timeline-item
                v-for="log in logs"
                :key="log.id"
                :type="getLogType(log.alert_level || 'info')"
                :timestamp="formatLogTime(log.time)"
                placement="top"
                size="large"
                @click="goToLogDetail(log)"
                style="cursor: pointer; transition: all 0.3s; padding: 12px 0;"
                @mouseenter="$event.currentTarget.style.backgroundColor = '#f5f7fa'"
                @mouseleave="$event.currentTarget.style.backgroundColor = 'transparent'"
              >
                <template #dot>
                  <!-- 自定义时间点圆圈，放大并左移 -->
                  <div class="custom-timeline-dot" :style="{ backgroundColor: getLogDotColor(log.alert_level) }"></div>
                </template>
                <div style="padding: 3px 8px 3px 20px;"> <!-- 左侧增加内边距，避免内容和圆圈重叠 -->
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <el-tag :type="getLogTagType(log.alert_level)" size="default" style="font-size: 14px; padding: 6px 12px;">
                      {{ getLogTagText(log.alert_level) }}
                    </el-tag>
                    <span style="font-size: 15px; color: #666; font-weight: 500;">{{ log.user || '未知用户' }}</span>
                  </div>
                  <div style="font-size: 16px; color: #333; line-height: 1.8; word-break: break-all; margin-bottom: 8px; font-weight: 500;">
                    {{ log.detail }}
                  </div>
                  <div style="font-size: 14px; color: #666; padding: 6px 10px; background: #f9f9f9; border-radius: 4px;">
                    行为类型：<strong style="color: #409EFF;">{{ log.type || '未知' }}</strong> &nbsp;|&nbsp;
                    异常分：<strong :style="{ color: log.anomaly_score > 60 ? '#F56C6C' : '#67C23A' }">{{ log.anomaly_score !== null && log.anomaly_score !== undefined ? log.anomaly_score.toFixed(1)  : 'N/A' }}</strong>
                  </div>
                </div>
              </el-timeline-item>
            </el-timeline>
            <div v-else style="text-align: center; color: #999; padding: 60px 0;">
              <el-icon style="font-size: 56px; margin-bottom: 15px;"><Document /></el-icon>
              <div style="font-size: 16px;">暂无日志</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { Document } from '@element-plus/icons-vue'

const router = useRouter()
const chartRef = ref(null)
let chartInstance = null
const selectedDay = ref('today')
const logs = ref([])

// 【新增】生成具体的日期选项
const dateOptions = computed(() => {
  const today = new Date()
  const formatDate = (date) => {
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }
  
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  
  const dayBeforeYesterday = new Date(today)
  dayBeforeYesterday.setDate(today.getDate() - 2)
  
  return [
    { label: formatDate(today), value: 'today' },
    { label: formatDate(yesterday), value: 'yesterday' },
    { label: formatDate(dayBeforeYesterday), value: 'dayBeforeYesterday' }
  ]
})

const stats = ref({
  total_devices: 0,
  high_risk_events: 0,
  blocked_events: 0,
  compliance_rate: '0%'
})

const fetchStats = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:5000/api/dashboard/stats')
    if (res.data.status === 'success') {
      stats.value = res.data.data
    }
  } catch (error) {
    console.error("Dashboard stats api error:", error)
  }
}

const fetchLogs = async () => {
  try {
    // 获取最新的10条日志
    const res = await axios.get('http://127.0.0.1:5000/api/behavior/logs', {
      params: { page: 1, per_page: 10 },
      timeout: 5000 // 5秒超时，避免长时间等待
    })
    if (res.data && res.data.code === 200 && res.data.data) {
      const logsData = res.data.data.logs || []
      logs.value = logsData.map(log => ({
        id: log.id,
        time: log.timestamp || log.time || '',
        user: log.user || '未知用户',
        type: log.behavior_type || log.type || '',
        detail: log.description || log.action_detail || log.detail || '',
        action_taken: log.action_taken,
        alert_level: log.alert_level,
        anomaly_score: log.anomaly_score
      }))
    }
  } catch (error) {
    console.error("获取日志失败:", error)
    logs.value = []
  }
}

const getLogType = (level) => {
  const map = {
    critical: 'danger',
    high: 'danger',
    medium: 'warning',
    low: 'success',
    info: 'info'
  }
  return map[level] || 'info'
}

const getLogTagType = (level) => {
  const map = {
    critical: 'danger',
    high: 'danger',
    medium: 'warning',
    low: 'success',
    info: 'info'
  }
  return map[level] || 'info'
}

const getLogTagText = (level) => {
  const map = {
    critical: '🚨 严重',
    high: '⚠️ 高危',
    medium: '⚡ 中危',
    low: '✅ 低危',
    info: 'ℹ️ 记录'
  }
  return map[level] || 'ℹ️ 记录'
}

// 新增：获取时间点圆圈颜色
const getLogDotColor = (level) => {
  const map = {
    critical: '#F56C6C',
    high: '#F56C6C',
    medium: '#E6A23C',
    low: '#67C23A',
    info: '#909399'
  }
  return map[level] || '#909399'
}

const formatLogTime = (timeStr) => {
  if (!timeStr) return '未知时间'
  // 格式化时间显示，去掉年份，只显示月-日 时:分
  try {
    const date = new Date(timeStr)
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    return `${month}-${day} ${hours}:${minutes}`
  } catch (e) {
    return timeStr
  }
}

const goToLogDetail = (log) => {
  // 跳转到日志详情页，带上日志ID
  router.push({
    path: '/admin/logs',
    query: {
      id: log.id,
      highlight: 'true' // 标记需要高亮显示
    }
  })
}

const getChartData = async (day) => {
  try {
    // 调用后端接口获取真实信任趋势数据
    const res = await axios.get('http://127.0.0.1:5000/api/dashboard/trust-trend', {
      params: { day: day }
    })
    if (res.data && res.data.status === 'success' && res.data.data) {
      return res.data.data.trust_scores
    }
    return []
  } catch (error) {
    console.error("获取信任趋势数据失败:", error)
    return []
  }
}

const updateChartData = async () => {
  if (chartInstance) {
    const data = await getChartData(selectedDay.value)
    chartInstance.setOption({
      series: [{
        data: data
      }]
    })
  }
}

onMounted(async () => {
  fetchStats()
  fetchLogs()

  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value)
    const option = {
      title: {
        text: '全终端信任度 24 小时变化曲线',
        left: 'center',
        top: '10',
        textStyle: { fontSize: 18, fontWeight: 'bold', color: '#333' }
      },
      tooltip: {
        trigger: 'axis',
        textStyle: { fontSize: 14 }
      },
      grid: {
        left: '4%',
        right: '4%',
        bottom: '5%',
        top: '60',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: Array.from({length: 24}, (_, i) => `${i.toString().padStart(2, '0')}:00`),
        boundaryGap: false,
        axisLabel: { fontSize: 14, color: '#666' }
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        axisLabel: { fontSize: 14, color: '#666' },
        splitLine: { lineStyle: { type: 'dashed', color: '#e0e0e0' } }
      },
      series: [
        {
          name: '平均信任分',
          type: 'line',
          data: [],  // 初始为空，稍后加载
          smooth: true,
          symbolSize: 8,
          lineStyle: { width: 3 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(64,158,255,0.5)' },
              { offset: 1, color: 'rgba(64,158,255,0.1)' }
            ])
          },
          itemStyle: { color: '#409EFF', borderWidth: 2 },
          markLine: {
            data: [{ yAxis: 60, name: '警告阈值', label: { formatter: '危险', fontSize: 15, color: '#F56C6C' } }],
            itemStyle: { color: '#F56C6C' },
            lineStyle: { width: 2, type: 'dashed' }
          }
        }
      ]
    }
    chartInstance.setOption(option)

    // 加载初始数据
    const initialData = await getChartData('today')
    chartInstance.setOption({
      series: [{ data: initialData }]
    })

    // Resize handler
    window.addEventListener('resize', () => {
      chartInstance?.resize()
    })
  }
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
  }
})
</script>

<style scoped>
.dashboard-wrapper {
  animation: fadeIn 0.5s;
}

/* Updated Uiverse.io Card Effect */
.card {
  display: block;
  position: relative;
  width: auto;
  max-width: 100%;
  max-height: 320px;
  background-color: #f2f8f9;
  border-radius: 10px;
  padding: 2em 1.2em;
  margin-bottom: 20px; /* adjusted for el-row */
  text-decoration: none;
  z-index: 0;
  overflow: hidden;
  background: linear-gradient(to bottom, #c3e6ec, #a7d1d9);
  font-family: Arial, Helvetica, sans-serif;
  text-align: center;
}

.card:before {
  content: '';
  position: absolute;
  z-index: -1;
  top: -16px;
  right: -16px;
  background: linear-gradient(135deg, #364a60, #384c6c);
  height: 32px;
  width: 32px;
  border-radius: 32px;
  transform: scale(1);
  transform-origin: 50% 50%;
  transition: transform 0.35s ease-out;
}

.card:hover:before {
  transform: scale(38); /* increased scale slightly for wider cards */
}

.card-title {
  color: #262626;
  font-size: 18px; /* 增大标题字号 */
  line-height: normal;
  font-weight: 700;
  margin-bottom: 0.8em;
  z-index: 10;
  position: relative;
}

.small-desc {
  font-size: 36px; /* 增大统计数字字号 */
  font-weight: bold;
  line-height: 1.5em;
  z-index: 10;
  position: relative;
}

.card:hover .small-desc, .card:hover .card-title {
  transition: all 0.5s ease-out;
  color: #ffffff !important;
}

.text-primary { color: #409EFF; }
.text-danger { color: #F56C6C; }
.text-warning { color: #E6A23C; }
.text-success { color: #67C23A; }

.go-corner {
  display: flex;
  align-items: center;
  justify-content: center;
  position: absolute;
  width: 2em;
  height: 2em;
  overflow: hidden;
  top: 0;
  right: 0;
  background: linear-gradient(135deg, #6293c8, #384c6c);
  border-radius: 0 10px 0 32px; /* matched parent radius */
}

.go-arrow {
  margin-top: -4px;
  margin-right: -4px;
  color: white;
  font-family: courier, sans;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 新增：自定义时间线样式 */
.custom-timeline {
  padding-left: 10px !important; /* 整体左移，让圆圈更靠左 */
}

.custom-timeline :deep(.el-timeline-item__node) {
  left: -15px !important; /* 强制将圆圈向左偏移 */
}

.custom-timeline-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 3px solid #fff;
  box-shadow: 0 0 0 2px currentColor;
}
</style>
<style>
/* Override element plus card backgrounds in dashboard to match new theme */
.dashboard-wrapper .el-card {
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(10px);
  border: none;
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
}
</style>