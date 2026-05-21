<template>
  <div class="baseline-container">
    <!-- 1. 头部释义区 -->
    <el-card shadow="hover" class="info-card">
      <div class="header-info">
        <h3>🎯 员工行为信任基线</h3>
        <p><strong>定义：</strong>员工正常办公行为的安全标准线，通过持续学习员工日常操作习惯生成。</p>
        <p><strong>作用：</strong>对比实时行为偏离度、自动计算并调整信任分、精准识别潜在内部异常与风险。</p>
        <p><strong>技术：</strong>WMA (加权移动平均) 算法追踪时间序列趋势 + 孤立森林 (Isolation Forest) 算法识别多维离群异常。</p>
      </div>
    </el-card>

    <!-- 3. 核心数据卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" body-style="padding: 20px; text-align: center;">
          <div class="stat-title">监管员工总数</div>
          <div class="stat-value text-primary">{{ tableData.length }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" body-style="padding: 20px; text-align: center;">
          <div class="stat-title">全员平均信任分</div>
          <div class="stat-value text-success">{{ averageScore }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" body-style="padding: 20px; text-align: center;">
          <div class="stat-title">高风险人数 (低于60分)</div>
          <div class="stat-value text-danger">{{ highRiskCount }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" body-style="padding: 20px; text-align: center;">
          <div class="stat-title">基线最后更新时间</div>
          <div class="stat-value" style="font-size: 20px; line-height: 38px; color: #666;">{{ updateTime }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 4. 简化可视化区 -->
    <el-row :gutter="20" class="charts-row">
      <el-col :span="12">
        <el-card shadow="hover" header="信任分区间分布">
          <div ref="distChartRef" style="height: 250px;"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover" header="各部门平均信任对比">
          <div ref="deptChartRef" style="height: 250px;"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 【新增】K-means聚类可视化 -->
    <el-card shadow="hover" header="📊 K-means岗位群组聚类分析" style="margin-top: 20px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
        <span style="color: #666; font-size: 14px;">系统自动将员工按行为特征分为 {{ clusterData.length }} 个岗位群组</span>
        <div>
          <el-button v-if="clusterData.length > 3" type="primary" link size="small" @click="showAllClusters = !showAllClusters">
            {{ showAllClusters ? '收起' : '展开全部' }}
          </el-button>
          <el-button type="primary" size="small" @click="loadClusterData" icon="Refresh" style="margin-left: 10px;">刷新聚类</el-button>
        </div>
      </div>

      <el-row :gutter="16" v-if="clusterData.length > 0">
        <el-col :span="8" v-for="(cluster, index) in displayedClusters" :key="cluster.cluster_id">
          <el-card shadow="hover" :body-style="{ padding: '12px' }" class="cluster-card">
            <div class="cluster-content">
              <!-- 群组名称 -->
              <div class="cluster-header">
                <span class="cluster-name">{{ cluster.cluster_name }}</span>
              </div>
              
              <!-- 成员数量 -->
              <div class="member-count">
                <span class="count-number">{{ cluster.member_count }}</span>
                <span class="count-label">成员数量</span>
              </div>

              <el-divider style="margin: 8px 0;" />

              <!-- 典型特征（重点突出） -->
              <div class="features-section">
                <div class="features-title">典型特征</div>
                <div class="features-list">
                  <div v-for="(value, key) in cluster.center_features" :key="key" class="feature-item">
                    <span class="feature-name">{{ formatFeatureName(key) }}</span>
                    <span class="feature-value">{{ typeof value === 'number' ? value.toFixed(1) : value }}</span>
                  </div>
                </div>
              </div>

              <el-divider style="margin: 8px 0;" />

              <!-- 部分成员 -->
              <div class="members-section">
                <div class="members-title">部分成员</div>
                <div class="members-tags">
                  <el-tag
                    v-for="member in cluster.members.slice(0, 5)"
                    :key="member.user_id"
                    size="small"
                    class="member-tag"
                  >
                    {{ member.name }}
                  </el-tag>
                  <span v-if="cluster.total_members > 5" class="more-members">
                    +{{ cluster.total_members - 5 }}人
                  </span>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-empty v-else description="暂无聚类数据，请点击刷新基线按钮进行训练" />
    </el-card>

    <!-- 2. 简化筛选区 -->
    <el-card shadow="never" class="table-card">
      <div class="filter-bar">
        <el-input v-model="filters.name" placeholder="请输入姓名搜索" style="width: 200px" clearable />
        <el-select v-model="filters.dept" placeholder="部门筛选" style="width: 200px" clearable>
          <el-option v-for="dept in depts" :key="dept" :label="dept" :value="dept" />
        </el-select>
        <el-select v-model="filters.status" placeholder="信任分筛选 (健康状态)" style="width: 200px" clearable>
          <el-option label="正常 (>=80)" value="正常" />
          <el-option label="警告 (60-79)" value="警告" />
          <el-option label="异常 (<60)" value="异常" />
        </el-select>
        <el-button type="primary" icon="Refresh" size="medium" class="refresh-btn" @click="refreshData">刷新基线</el-button>
      </div>

      <!-- 5. 精简表格 -->
      <el-table :data="paginatedData" style="width: 100%" v-loading="loading">
        <el-table-column prop="name" label="姓名" width="150" />
        <el-table-column prop="dept" label="部门" width="180" />
        <el-table-column prop="score" label="当前信任分" width="120" align="center">
          <template #default="scope">
            <span :style="{ color: scope.row.score >= 80 ? '#67C23A' : (scope.row.score >= 60 ? '#E6A23C' : '#F56C6C'), fontWeight: 'bold' }">
              {{ scope.row.score }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="health" label="健康状态" width="120" align="center">
          <template #default="scope">
            <el-tag :type="scope.row.health === '正常' ? 'success' : (scope.row.health === '警告' ? 'warning' : 'danger')" effect="dark" size="small">
              {{ scope.row.health }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="anomalyCount" label="本月异常次数" width="150" align="center" />
        <el-table-column prop="lastUpdate" label="更新时间" />
        <el-table-column label="操作" width="140" align="center" fixed="right">
          <template #default="scope">
            <el-button link type="primary" size="small" class="small-detail-btn" @click="showDetails(scope.row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 20px; display: flex; justify-content: flex-end;">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="filteredData.length"
          v-model:current-page="currentPage"
          :page-size="pageSize"
        />
      </div>
    </el-card>

    <!-- 6. 员工详情弹窗 -->
    <el-dialog v-model="dialogVisible" title="员工基线详情" width="700px" class="detail-dialog">
      <div v-if="currentRow" class="detail-content">
        <div class="basic-info">
          <el-descriptions border :column="2" size="default">
            <el-descriptions-item label="姓名">{{ currentRow.name }}</el-descriptions-item>
            <el-descriptions-item label="部门">{{ currentRow.dept }}</el-descriptions-item>
            <el-descriptions-item label="当前信任分">
              <span :style="{ color: currentRow.score >= 80 ? '#67C23A' : (currentRow.score >= 60 ? '#E6A23C' : '#F56C6C'), fontWeight: 'bold' }">
                {{ currentRow.score }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="健康状态">
              <el-tag :type="currentRow.health === '正常' ? 'success' : (currentRow.health === '警告' ? 'warning' : 'danger')" size="small">
                {{ currentRow.health }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="chart-section" style="margin-top: 20px;">
          <h4>📈 员工信任分变化趋势（近14天）</h4>
          <div ref="detailChartRef" style="height: 250px;" v-loading="wmaLoading"></div>
          <div class="chart-explain" style="margin-top: 8px; padding: 8px; background-color: #f0f9ff; border-left: 3px solid #409EFF; border-radius: 4px; font-size: 13px; color: #666;">
            <strong>图表说明：</strong>本曲线展示该员工近14天每日信任分平均值变化，反映信任状态趋势。低于60分触发异常告警，低于80分触发预警。
          </div>
        </div>

        <div class="algo-explain" style="margin-top: 15px; padding: 10px; background-color: #f4f4f5; border-radius: 4px; font-size: 15px;">
          <strong> 基线算法说明：</strong>
          <p style="margin: 5px 0 0 0; color: #666;">
            系统采用 <strong>WMA (加权移动平均)</strong> 算法，结合行为异常分和上下文环境，动态计算每日信任分。近期行为数据权重更高，实时反映信任状态变化。
          </p>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue';
import * as echarts from 'echarts';
import axios from 'axios';

const currentPage = ref(1)
const pageSize = ref(10)
const loading = ref(false)

// 【新增】聚类数据
const clusterData = ref([])
const showAllClusters = ref(false) // 控制是否展开全部群组

// 计算显示的群组（默认显示前3个）
const displayedClusters = computed(() => {
  if (showAllClusters.value || clusterData.value.length <= 3) {
    return clusterData.value
  }
  return clusterData.value.slice(0, 3)
})

// 【新增】WMA曲线相关
const selectedUserForCurve = ref(null)
const wmaChartRef = ref(null)
let wmaChart = null

const filters = ref({
  name: '',
  dept: '',
  status: ''
})

const depts = ref([]) // 【修复】改为动态数组，不再写死部门名称
const tableData = ref([]);

const filteredData = computed(() => {
  return tableData.value.filter(item => {
    let match = true;
    if (filters.value.name && !item.name.includes(filters.value.name)) match = false;
    if (filters.value.dept && item.dept !== filters.value.dept) match = false;
    if (filters.value.status && item.health !== filters.value.status) match = false;
    return match;
  });
})

const paginatedData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredData.value.slice(start, end)
})

// Metrics computation
const averageScore = computed(() => {
  if (tableData.value.length === 0) return 0;
  const sum = tableData.value.reduce((acc, curr) => acc + curr.score, 0);
  return (sum / tableData.value.length).toFixed(1);
})

const highRiskCount = computed(() => {
  return tableData.value.filter(item => item.score < 60).length;
})

const updateTime = ref(new Date().toLocaleString('zh-CN'))

const refreshData = async () => {
  loading.value = true;
  try {
    const token = localStorage.getItem('sys_token');

    // 1. 调用后端重新训练基线
    await axios.post('/api/baseline/rebuild', {}, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    // 2. 获取真实用户数据
    const response = await axios.get('/api/baseline/users', {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (response.data.code === 200) {
      const users = response.data.data || [];
      tableData.value = users.map(user => ({
        id: `EMP${user.id.toString().padStart(3, '0')}`,
        name: user.name,
        dept: user.department ? user.department.trim() : '未知', // 【修改】去除可能存在的空格
        score: user.trust_score || 100,
        health: user.trust_score >= 80 ? '正常' : (user.trust_score >= 60 ? '警告' : '异常'),
        anomalyCount: 0,
        lastUpdate: new Date().toLocaleTimeString('zh-CN', { hour12: false })
      }));

      // ======== 【核心修复】动态提取、去空格并精准去重所有真实的部门名称 ========
      const allDepts = tableData.value.map(item => item.dept);
      depts.value = [...new Set(allDepts)].filter(d => d && d !== '未知' && d !== '');
      // ======================================================================

      updateTime.value = new Date().toLocaleString('zh-CN');
      initCharts();
      loadClusterData();
    }
  } catch (error) {
    console.error('刷新基线失败:', error);
    alert('刷新基线失败，请检查后端服务是否启动');
  } finally {
    loading.value = false;
  }
}

// Dialog
const dialogVisible = ref(false)
const currentRow = ref(null)
const detailChartRef = ref(null)
const wmaLoading = ref(false)

const showDetails = async (row) => {
  currentRow.value = row;
  dialogVisible.value = true;

  // 提取用户ID（从EMP001格式中提取数字）
  const userId = parseInt(row.id.replace('EMP', ''));

  nextTick(() => {
    initWMAChart(userId);
  });
}

// 【优化】初始化信任分趋势曲线
const initWMAChart = async (userId) => {
  if (!detailChartRef.value) return;

  wmaLoading.value = true;

  try {
    const token = localStorage.getItem('sys_token');
    const response = await axios.get(`/api/baseline/user/${userId}/wma`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (response.data.code === 200 && response.data.data.daily_trust_trend.length > 0) {
      const trendData = response.data.data.daily_trust_trend;

      if (detailChart) detailChart.dispose();
      detailChart = echarts.init(detailChartRef.value);

      // 【修复】按日期升序排列，确保时间从左到右递增
      const dates = trendData.map(item => item.date);
      const avgScores = trendData.map(item => item.avg_trust_score);
      const minScores = trendData.map(item => item.min_score);
      const maxScores = trendData.map(item => item.max_score);

      detailChart.setOption({
        title: {
          text: `员工信任分变化趋势（${trendData[0].date} ~ ${trendData[trendData.length - 1].date}）`,
          left: 'center',
          textStyle: { fontSize: 16, color: '#606266' }
        },
        tooltip: {
          trigger: 'axis',
          formatter: (params) => {
            const idx = params[0].dataIndex;
            const item = trendData[idx];
            return `
              <div style="padding: 5px; font-size: 14px;">
                <strong>${item.date}</strong><br/>
                平均信任分: <strong>${item.avg_trust_score}</strong><br/>
                当日最低分: ${item.min_score}<br/>
                当日最高分: ${item.max_score}<br/>
                行为次数: ${item.behavior_count}<br/>
                高风险行为: ${item.high_risk_count}
              </div>
            `;
          }
        },
        legend: {
          data: ['平均信任分', '最低分', '最高分'],
          top: 30
        },
        grid: { left: '10%', right: '5%', bottom: '15%', top: '60px' },
        xAxis: {
          type: 'category',
          data: dates,
          axisLabel: { 
            rotate: 45, 
            fontSize: 12,
            formatter: (value) => value.substring(5) // 只显示 MM-DD
          }
        },
        yAxis: {
          type: 'value',
          min: 0,
          max: 100,
          name: '信任分',
          nameTextStyle: { fontSize: 14 },
          axisLabel: { fontSize: 12 },
          splitLine: { lineStyle: { type: 'dashed' } }
        },
        series: [
          {
            name: '平均信任分',
            type: 'line',
            data: avgScores,
            smooth: true,
            itemStyle: { color: '#409EFF' },
            lineStyle: { width: 3 },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(64,158,255,0.3)' },
                { offset: 1, color: 'rgba(64,158,255,0.05)' }
              ])
            },
            markLine: {
              data: [
                { yAxis: 60, name: '异常阈值(60)', lineStyle: { color: '#F56C6C', type: 'dashed' } },
                { yAxis: 80, name: '预警阈值(80)', lineStyle: { color: '#E6A23C', type: 'dashed' } }
              ],
              label: { fontSize: 12 }
            }
          },
          {
            name: '最低分',
            type: 'line',
            data: minScores,
            lineStyle: { type: 'dashed', width: 1 },
            itemStyle: { color: '#909399' }
          },
          {
            name: '最高分',
            type: 'line',
            data: maxScores,
            lineStyle: { type: 'dashed', width: 1 },
            itemStyle: { color: '#67C23A' }
          }
        ]
      });
    } else {
      // 无数据时显示空状态
      if (detailChart) detailChart.dispose();
      detailChart = echarts.init(detailChartRef.value);
      detailChart.setOption({
        title: {
          text: '暂无行为数据',
          left: 'center',
          top: 'center',
          textStyle: { color: '#909399', fontSize: 16 }
        }
      });
    }
  } catch (error) {
    console.error('获取信任分趋势失败:', error);
  } finally {
    wmaLoading.value = false;
  }
}

// Charts
const distChartRef = ref(null)
const deptChartRef = ref(null)
let distChart = null;
let deptChart = null;
let detailChart = null;

const initCharts = () => {
  if (!distChartRef.value || !deptChartRef.value) return;

  // Distribution Chart
  const normalCount = tableData.value.filter(i => i.score >= 80).length;
  const warningCount = tableData.value.filter(i => i.score >= 60 && i.score < 80).length;
  const dangerCount = tableData.value.filter(i => i.score < 60).length;

  distChart = echarts.init(distChartRef.value);
  distChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: ['高风险 (<60)', '警告 (60-79)', '健康 (>=80)'],
      axisLabel: { fontSize: 14 }
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 14 }
    },
    series: [
      {
        type: 'bar',
        data: [
          { value: dangerCount, itemStyle: { color: '#F56C6C' } },
          { value: warningCount, itemStyle: { color: '#E6A23C' } },
          { value: normalCount, itemStyle: { color: '#67C23A' } }
        ],
        barWidth: '40%',
        label: { show: true, fontSize: 14 }
      }
    ]
  });

  // Department Average Chart
  // 【核心修复】遍历动态部门，同时计算平均分与该部门在 tableData 中的真实总人数
  const deptAvg = depts.value.map(dept => {
    const employees = tableData.value.filter(i => i.dept === dept);
    const avg = employees.length ? employees.reduce((acc, curr) => acc + curr.score, 0) / employees.length : 0;
    return {
      name: dept,
      value: parseFloat(avg.toFixed(1)),
      count: employees.length // 👈 【新增】实时计算并保存该部门的真实总人数
    };
  });

  deptChart = echarts.init(deptChartRef.value);
  deptChart.setOption({
    tooltip: {
      trigger: 'axis',
      // 👈 【新增】悬浮提示框自定义：同时清晰展示平均分和部门总人数
      formatter: function (params) {
        const item = deptAvg[params[0].dataIndex];
        return `<strong>🏢 ${item.name}</strong><br/>
                平均信任分：<span style="color:#409EFF;font-weight:bold;">${item.value} 分</span><br/>
                部门总人数：<span style="color:#67C23A;font-weight:bold;">${item.count} 人</span>`;
      }
    },
    grid: { left: '3%', right: '15%', bottom: '3%', top: '10%', containLabel: true }, // 适当拉大右边距防止文字溢出
    xAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { fontSize: 14 }
    },
    yAxis: {
      type: 'category',
      data: deptAvg.map(item => item.name),
      axisLabel: { fontSize: 14 }
    },
    series: [
      {
        type: 'bar',
        data: deptAvg.map((item) => ({
          value: item.value,
          itemStyle: { color: item.value < 70 ? '#E6A23C' : '#409EFF' }
        })),
        // 👈 【修改】让柱状图右侧的标签同时标注 分数 和 部门人数，一目了然
        label: {
          show: true,
          position: 'right',
          fontSize: 13,
          formatter: function(params) {
            const item = deptAvg[params.dataIndex];
            return `${item.value}分 (${item.count}人)`;
          }
        }
      }
    ]
  }, true); // 👈 【⚡至关重要】传入 true 开启 notMerge 模式，彻底粉碎 ECharts 缓存造成的残留脏数据！
}

const initDetailChart = (row) => {
  if (!detailChartRef.value) return;

  if (detailChart) detailChart.dispose();
  detailChart = echarts.init(detailChartRef.value);

  // mock 30 days data ending at current score
  const days = Array.from({length: 30}, (_, i) => `Day ${i+1}`);
  let lastScore = row.score > 90 ? 100 : row.score + Math.floor(Math.random() * 20);
  const data = days.map((_, i) => {
    if (i === 29) return row.score;
    lastScore = Math.max(30, Math.min(100, lastScore + (Math.random() * 10 - 5)));
    return lastScore.toFixed(0);
  });

  detailChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '10%', right: '5%', bottom: '15%', top: '10%' },
    xAxis: { type: 'category', data: days, show: false },
    yAxis: { type: 'value', min: 0, max: 100 },
    series: [{
      name: '信任分',
      type: 'line',
      data: data,
      smooth: true,
      itemStyle: { color: '#409EFF' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(64,158,255,0.3)' },
          { offset: 1, color: 'rgba(64,158,255,0.05)' }
        ])
      }
    }]
  });
}

// 【新增】加载聚类数据
const loadClusterData = async () => {
  try {
    const token = localStorage.getItem('sys_token');
    const response = await axios.get('/api/baseline/clusters/visualization', {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (response.data.code === 200) {
      clusterData.value = response.data.data.clusters;
      console.log('✅ 聚类数据加载成功:', clusterData.value.length, '个群组');
    } else {
      console.warn('⚠️ 聚类数据未就绪:', response.data.message);
    }
  } catch (error) {
    console.error('❌ 加载聚类数据失败:', error);
  }
}

// 【新增】格式化特征名称
const formatFeatureName = (key) => {
  const nameMap = {
    'file_ops': '文件操作频次',
    'usb_access': 'USB设备使用',
    'login_hours': '登录时长(小时)',
    'email_sent': '邮件发送数',
    'browser_visits': '浏览器访问'
  };
  return nameMap[key] || key;
}

onMounted(async () => {
  // 页面加载时自动获取真实数据
  await refreshData();

  window.addEventListener('resize', () => {
    distChart?.resize();
    deptChart?.resize();
    detailChart?.resize();
  });
})
</script>

<style scoped>
.baseline-container {
  padding: 20px;
  background-color: #f5f7fa;
  min-height: 100vh;
}
.info-card {
  margin-bottom: 20px;
  background: linear-gradient(135deg, #e0f2f1 0%, #b2dfdb 100%);
  border: none;
}
.header-info h3 {
  margin-top: 0;
  color: #00695c;
  margin-bottom: 15px;
  font-size: 22px;
}
.header-info p {
  margin: 5px 0;
  color: #333;
  font-size: 16px;
}
.stat-cards {
  margin-bottom: 20px;
}
.stat-title {
  color: #909399;
  font-size: 16px;
  margin-bottom: 10px;
}
.stat-value {
  font-size: 32px;
  font-weight: bold;
}
.text-primary { color: #409EFF; }
.text-success { color: #67C23A; }
.text-danger { color: #F56C6C; }

.charts-row {
  margin-bottom: 20px;
}

.table-card {
  border-radius: 8px;
}
.filter-bar {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
  align-items: center;
}

/* ==================== 统一筛选组件样式 ==================== */
/* 输入框和下拉框的统一样式 */
:deep(.filter-bar .el-input),
:deep(.filter-bar .el-select) {
  width: 200px !important;
}

:deep(.filter-bar .el-input .el-input__wrapper),
:deep(.filter-bar .el-select .el-input__wrapper) {
  height: 40px !important;
  border-radius: 6px !important;
  box-shadow: 0 0 0 1px #dcdfe6 inset !important;
}

:deep(.filter-bar .el-input__inner),
:deep(.filter-bar .el-select .el-input__inner) {
  height: 40px !important;
  line-height: 40px !important;
  font-size: 16px !important;
  color: #303133 !important;
  font-weight: 500;
}

:deep(.filter-bar .el-input__inner::placeholder),
:deep(.filter-bar .el-select .el-input__inner::placeholder) {
  color: #a8abb2 !important;
  font-size: 15px !important;
}

:deep(.filter-bar .el-input__icon),
:deep(.filter-bar .el-select .el-input .el-select__caret) {
  font-size: 16px !important;
  line-height: 40px !important;
  color: #a8abb2 !important;
}

/* ==================== 刷新基线按钮样式 ==================== */
.refresh-btn {
  height: 40px !important;
  padding: 0 20px !important;
  font-size: 15px !important;
  font-weight: 600 !important;
  border-radius: 6px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  gap: 6px !important;
}

/* 查看详情按钮缩小样式 */
.small-detail-btn {
  padding: 4px 12px !important;
  font-size: 13px !important;
  border-radius: 6px !important;
  line-height: 1.4 !important;
}

h4 {
  margin: 0 0 10px 0;
  color: #606266;
  font-size: 18px;
}

/* 表格字体放大 */
:deep(.el-table) {
  font-size: 16px;
}
:deep(.el-table th) {
  font-size: 16px;
}
:deep(.el-table td) {
  font-size: 16px;
}

/* 分页字体放大 */
:deep(.el-pagination) {
  font-size: 16px;
}

/* 卡片标题字体放大 */
:deep(.el-card__header) {
  font-size: 18px;
}

/* 描述列表字体放大 */
:deep(.el-descriptions__label) {
  font-size: 16px;
}
:deep(.el-descriptions__content) {
  font-size: 16px;
}

/* K-means聚类卡片样式优化 */
.cluster-card {
  height: 100%;
  transition: all 0.3s ease;
}

.cluster-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.cluster-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cluster-header {
  text-align: center;
  margin-bottom: 4px;
}

.cluster-name {
  font-size: 16px;
  font-weight: bold;
  color: #409EFF;
}

.member-count {
  text-align: center;
  padding: 8px 0;
}

.count-number {
  display: block;
  font-size: 28px;
  font-weight: bold;
  color: #67C23A;
  line-height: 1;
}

.count-label {
  display: block;
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

/* 典型特征区域（重点突出） */
.features-section {
  flex: 1;
}

.features-title {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 10px;
  padding-bottom: 4px;
  border-bottom: 2px solid #409EFF;
  display: inline-block;
}

.features-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.feature-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: 16px;
}

.feature-name {
  color: #606266;
  font-weight: 500;
  font-size: 16px;
}

.feature-value {
  color: #409EFF;
  font-weight: bold;
  font-size: 18px;
}

/* 成员区域 */
.members-section {
  margin-top: 4px;
}

.members-title {
  font-size: 13px;
  font-weight: bold;
  color: #606266;
  margin-bottom: 6px;
}

.members-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.member-tag {
  margin: 0 !important;
}

.more-members {
  font-size: 12px;
  color: #999;
  margin-left: 4px;
}
</style>