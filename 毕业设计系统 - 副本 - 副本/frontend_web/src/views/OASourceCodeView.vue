<template>
  <div class="oa-sourcecode-container">
    <el-card class="oa-card">
      <template #header>
        <div class="card-header">
          <h2><el-icon><Monitor /></el-icon> 集团核心 Git 源码库</h2>     
          <div class="header-actions">
            <!-- 【新增】高信任解锁批量下载 -->
            <el-button
              v-if="trustScore >= 80"
              type="success"
              size="small"
              @click="batchDownload"
            >
              批量克隆全部
            </el-button>
            <el-button @click="$router.push('/portal/oa')">断开连接并返回</el-button>
          </div>
        </div>
      </template>

      <!-- 【新增】信任分提示 -->
      <el-alert
        :title="trustScore >= 80 ? '当前信任分优秀，已解锁源码克隆/下载权限' : '当前信任分良好，仅支持浏览'"
        :type="trustScore >= 80 ? 'success' : 'warning'"
        show-icon
        style="margin-bottom: 20px;"
        :closable="false"
      />

      <el-table :data="tableData" style="width: 100%" border v-loading="loading">
        <el-table-column prop="repo" label="仓库名称" width="250" />
        <el-table-column prop="desc" label="描述" />
        <el-table-column prop="update" label="最后更新" width="180" />
        <el-table-column label="操作" width="180" align="center">
          <template #default="scope">
            <el-button
              size="small"
              type="primary"
              plain
              :disabled="trustScore < 80"
              @click="downloadCode(scope.row.repo)"
            >
              克隆/下载
              <el-tag v-if="trustScore < 80" type="info" size="small" style="margin-left: 5px;">需 ≥80</el-tag>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { Monitor } from '@element-plus/icons-vue'
import axios from 'axios'

const loading = ref(false)
const trustScore = ref(0)

const tableData = ref([
  {
    repo: 'remote-office-guard-system',
    desc: '远程办公防护系统核心引擎 (Python / Flask)',
    update: '2026-03-24'
  },
  {
    repo: 'backend-auth-service',
    desc: '统一身份认证微服务集群',
    update: '2026-03-23'
  },
  {
    repo: 'financial-data-analysis',
    desc: '内部财务数据风控与预测模型 (绝密)',
    update: '2026-03-21'
  }
])

const getToken = () => localStorage.getItem('sys_token')

const fetchTrustScore = async () => {
    try {
        const token = getToken()
        const res = await axios.get('http://127.0.0.1:5000/api/auth/me', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
        trustScore.value = res.data.data.trust_score
    } catch(e) {}
}

const triggerRealDownload = (repoName, content) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${repoName}-master.zip`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
}

const downloadCode = async (repoName) => {
  if (trustScore.value < 80) {
    ElMessage.warning('信任分不足 80，无法下载核心源码')
    return
  }

  loading.value = true
  try {
    // 尝试记录行为日志
    try {
        await axios.post('http://127.0.0.1:5000/api/behavior/report', {
            type: 'events',
            data: {
                event_type: 'file_copy',
                severity: 'high',
                timestamp: new Date().toISOString(),
                description: `请求下载核心源码: ${repoName}`
            }
        }, { headers: { 'Authorization': 'Bearer ' + getToken() } })
    } catch (logError) {
        console.warn('行为日志上报失败，但不影响下载:', logError)
    }

    ElNotification({
        title: '审计系统提示',
        message: '检测到 Git Clone 操作，当前信任值较高，已放行并开始下载。',
        type: 'success',
    })

    const fakeZipContent = `This is a mock zip file content for repository: ${repoName}\nDownloaded at: ${new Date().toLocaleString()}\nZero Trust Protected.`

    setTimeout(() => {
        triggerRealDownload(repoName, fakeZipContent)
        loading.value = false
    }, 1500)

  } catch (error) {
     ElNotification({
        title: '下载失败',
        message: '系统发生未知错误，请稍后再试。',
        type: 'error',
    })
    loading.value = false
  }
}

const batchDownload = () => {
    ElMessage.success('批量任务已加入队列，因信任分优秀，已优先处理')
    // 模拟批量下载
    tableData.value.forEach(row => {
        setTimeout(() => {
            triggerRealDownload(row.repo, `Batch download content for ${row.repo}`)
        }, 500)
    })
}

onMounted(() => {
    fetchTrustScore()
})
</script>

<style scoped>
.oa-card {
  max-width: 900px;
  margin: 0 auto;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
    display: flex;
    gap: 10px;
}
</style>