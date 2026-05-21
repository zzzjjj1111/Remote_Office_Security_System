<template>
  <div class="simulator-wrapper">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>终端状态打标仿真 (免部署探针)</span>
        </div>
      </template>

      <el-form label-width="140px">
        <el-form-item label="终端运行环境打分">
          <el-slider v-model="form.env_score" :step="10" show-stops />
        </el-form-item>

        <el-form-item label="杀毒软件状态">
          <el-switch v-model="form.antivirus_active" active-text="运行中" inactive-text="已关闭" />
        </el-form-item>

        <el-form-item label="防火墙状态">
          <el-switch v-model="form.firewall_active" active-text="已开启" inactive-text="已关闭" />
        </el-form-item>

        <el-form-item label="系统补丁更新">
          <el-switch v-model="form.os_patches_up_to_date" active-text="最新" inactive-text="未更新" />
        </el-form-item>

        <el-divider>行为注入测试库</el-divider>

        <el-form-item label="U盘接入事件">
          <el-button @click="sendEvent('usb_insert')" type="warning" plain>模拟: 插入未授权U盘</el-button>
        </el-form-item>

        <el-form-item label="机密文件泄露">
          <el-button @click="sendEvent('file_copy')" type="danger" plain>模拟: 大量拷贝源码</el-button>
        </el-form-item>

        <el-divider>快速一键变更</el-divider>

        <el-button type="success" @click="setAll(true, 100)" class="w-full mb-2">一键设置: 安全状态 (100分)</el-button>
        <el-button type="danger" @click="setAll(false, 30)" class="w-full">一键设置: 危险状态 (30分)</el-button>
        
        <div class="mt-4 text-center">
            <el-button type="primary" size="large" @click="submitState" :loading="loading" style="width: 200px">提交状态上报</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const loading = ref(false)

const form = reactive({
  env_score: 90,
  antivirus_active: true,
  firewall_active: true,
  os_patches_up_to_date: true
})

const setAll = (status, score) => {
  form.antivirus_active = status
  form.firewall_active = status
  form.os_patches_up_to_date = status
  form.env_score = score
}

const getToken = () => localStorage.getItem('sys_token')

const submitState = async () => {
    loading.value = true
    try {
        await axios.post('http://127.0.0.1:5000/api/behavior/report', {
            type: 'metrics',
            data: {
                cpu_usage: Math.random() * 20 + 10,
                memory_usage: Math.random() * 30 + 30,
                disk_io_rate: Math.random() * 5 + 1
            }
        }, { headers: { 'Authorization': 'Bearer ' + getToken() } })

         await axios.post('http://127.0.0.1:5000/api/behavior/report', {
            type: 'environment',
            data: {
                antivirus_active: form.antivirus_active,
                firewall_active: form.firewall_active,
                os_patches_up_to_date: form.os_patches_up_to_date,
                score: form.env_score
            }
        }, { headers: { 'Authorization': 'Bearer ' + getToken() } })
        ElMessage.success('配置已生效，环境已变更')
    } catch(e) {
        ElMessage.error('上报失败: ' + (e.response?.data?.message || e.message))
    }
    loading.value = false
}

const sendEvent = async (type) => {
    try {
        await axios.post('http://127.0.0.1:5000/api/behavior/report', {
            type: 'events',
            data: {
                event_type: type,
                severity: 'high',
                timestamp: new Date().toISOString()
            }
        }, { headers: { 'Authorization': 'Bearer ' + getToken() } })
        ElMessage.warning('行为事件注入成功: ' + type)
    } catch(e) {
        ElMessage.error('注入失败: ' + (e.response?.data?.message || e.message))
    }
}
</script>

<style scoped>
.simulator-wrapper {
  padding: 20px;
}
.card-header {
  font-weight: bold;
}
.w-full {
    width: 100%;
}
.mb-2 {
    margin-bottom: 8px;
}
.mt-4 {
    margin-top: 16px;
}
</style>
