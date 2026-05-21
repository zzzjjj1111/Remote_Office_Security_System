<template>
  <div class="dashboard-container">
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>终端安全概览</span>
            </div>
          </template>
          <div class="overview-data">
            <p>活跃终端数：<strong>12</strong></p>
            <p>今日异常告警：<span style="color: red;">3</span> 次</p>
            <p>被阻断高风险操作：<span style="color: red;">1</span> 次</p>
          </div>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>员工信任值监控曲线 (动态行为基线)</span>
            </div>
          </template>
          <div ref="chartRef" style="height: 300px; width: 100%;"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row style="margin-top: 20px;">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>近期异常阻断记录 (模拟数据)</span>
            </div>
          </template>
          <el-table :data="tableData" style="width: 100%" stripe>
            <el-table-column prop="date" label="时间" width="180" />
            <el-table-column prop="name" label="姓名" width="120" />
            <el-table-column prop="department" label="部门" width="120" />
            <el-table-column prop="behavior" label="异常行为描述" />
            <el-table-column prop="risk" label="风险等级" width="100">
              <template #default="scope">
                <el-tag :type="scope.row.risk === 'Critical' ? 'danger' : 'warning'">
                  {{ scope.row.risk }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="action" label="处理动作" width="100">
               <template #default="scope">
                <el-tag :type="scope.row.action === 'Block' ? 'danger' : 'info'">
                  {{ scope.row.action }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'

const chartRef = ref(null)

const tableData = ref([
  {
    date: '2026-03-23 10:22:15',
    name: '张三',
    department: '研发部',
    behavior: 'U盘拷贝包含[核心源码]的文件',
    risk: 'Critical',
    action: 'Block'
  },
  {
    date: '2026-03-23 09:15:30',
    name: '李四',
    department: '销售部',
    behavior: '脱离基线：短时间内高频下载客户资料',
    risk: 'High',
    action: 'Warn'
  }
])

onMounted(() => {
  if (chartRef.current) {
    chartRef.current.dispose && chartRef.current.dispose();
  }
  const myChart = echarts.init(chartRef.value)
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['张三(研发)', '李四(销售)'] },
    xAxis: {
      type: 'category',
      data: ['08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00']
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      name: 'Trust Score'
    },
    series: [
      {
        name: '张三(研发)',
        type: 'line',
        data: [100, 100, 100, 90, 90, 80, 70],
        smooth: true,
        lineStyle: { width: 3 }
      },
      {
        name: '李四(销售)',
        type: 'line',
        data: [100, 95, 95, 95, 90, 90, 90],
        smooth: true,
        lineStyle: { width: 3 }
      }
    ]
  }
  myChart.setOption(option)
  
  window.addEventListener('resize', () => {
    myChart.resize()
  })
})
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
}
.overview-data p {
  font-size: 16px;
  line-height: 2;
}
</style>
