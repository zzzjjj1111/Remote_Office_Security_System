<template>
  <div style="padding: 20px">
    <!-- Algorithm Config -->
    <el-card shadow="never" style="margin-bottom: 20px;">
      <template #header>
        <div class="header-title">
          <el-icon color="#409EFF"><Setting /></el-icon> 核心算法参数调节
        </div>
      </template>
      <el-form label-position="top">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="高风险阈值 (分)/ trust_threshold">
              <el-input-number v-model="form.isolationForestThreshold" style="width: 100%" />
              <div class="help-text">异常评分超过此值将直接触发阻断并扣减信任值。</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="近 3 天权重系数/ wma_weight">
              <el-input-number v-model="form.wmaWeight" :step="0.1" :max="1" :min="0" style="width: 100%" />
              <div class="help-text">动态调整基线时，近期操作行为的加权比例。（0.1 ~ 1.0）</div>
            </el-form-item>
          </el-col>
        </el-row>
        <div style="text-align: right; margin-top: 15px;">
          <button type="button" class="custom-btn" @click="saveConfig">保存参数配置</button>
        </div>
      </el-form>
    </el-card>

    <!-- 工作时间配置 -->
    <el-card shadow="never" style="margin-bottom: 20px;">
      <template #header>
        <div class="header-title">
          <el-icon color="#67C23A"><Clock /></el-icon> 工作时间配置
        </div>
      </template>
      <el-form label-position="top">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="工作开始时间">
              <el-time-picker
                v-model="workTime.start"
                format="HH:mm"
                value-format="HH:mm"
                placeholder="选择时间"
                style="width: 100%"
              />
              <div class="help-text">设置工作日开始时间，非工作时间操作将被标记为异常。</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工作结束时间">
              <el-time-picker
                v-model="workTime.end"
                format="HH:mm"
                value-format="HH:mm"
                placeholder="选择时间"
                style="width: 100%"
              />
              <div class="help-text">设置工作日结束时间，非工作时间操作将被标记为异常。</div>
            </el-form-item>
          </el-col>
        </el-row>
        <div style="text-align: right; margin-top: 15px;">
          <button type="button" class="custom-btn" @click="saveWorkTime">保存工作时间</button>
        </div>
      </el-form>
    </el-card>

    <!-- AC Automaton Dictionary Management -->
    <el-card shadow="never">
      <template #header>
        <div class="header-title">
          <el-icon color="#F56C6C"><Lock /></el-icon> 敏感词库管理
        </div>
      </template>

      <div style="margin-bottom: 20px; display: flex; gap: 10px;">
        <el-input v-model="newWord" placeholder="输入敏感词 (如: 财务报表、核心源码)" style="width: 300px;"></el-input>
        <el-select v-model="newCategory" placeholder="风险等级" style="width: 120px;">
          <el-option label="绝密" value="绝密" />
          <el-option label="高风险" value="高风险" />
          <el-option label="中风险" value="中风险" />
        </el-select>
        <button type="button" class="custom-btn" @click="addWord" style="margin-left:auto;"><el-icon style="margin-right:4px"><Plus /></el-icon> 添加特征词</button>
      </div>

      <el-table :data="wordList" style="width: 100%" border>
        <el-table-column prop="word" label="敏感词/特征符" />
        <el-table-column prop="risk" label="风险定级" width="130">
          <template #default="scope">
            <el-tag 
              :type="scope.row.risk === '绝密' ? 'danger' : (scope.row.risk === '高风险' ? 'warning' : 'info')"
              effect="plain"
            >
              {{ scope.row.risk }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="creator" label="创建人ID" width="120" />
        <el-table-column prop="time" label="添加时间" width="180" />
        <el-table-column label="操作" width="110" align="center">
          <template #default="scope">
            <button class="del-button" type="button" @click="removeWord(scope.row.id)">
              <svg viewBox="0 0 448 512" class="svgIcon"><path d="M135.2 17.7L128 32H32C14.3 32 0 46.3 0 64S14.3 96 32 96H416c17.7 0 32-14.3 32-32s-14.3-32-32-32H320l-7.2-14.3C307.4 6.8 296.3 0 284.2 0H163.8c-12.1 0-23.2 6.8-28.6 17.7zM416 128H32L53.2 467c1.6 25.3 22.6 45 47.9 45H346.9c25.3 0 46.3-19.7 47.9-45L416 128z"></path></svg>
            </button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
// 🔥 修复1：补充导入 onMounted（解决页面空白核心问题）
import { ref, reactive, onMounted } from 'vue'
import { Setting, Lock, Plus, Clock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

// 算法参数
const form = reactive({
  isolationForestThreshold: 60,
  wmaWeight: 0.5
})

// 🔥 修复2：对接后端保存算法参数
const saveConfig = async () => {
  try {
    await axios.post('/api/config/update', {
      trust_threshold: form.isolationForestThreshold,
      wma_weight: form.wmaWeight
    })
    ElMessage.success('算法参数保存成功！将实时下发生效。')
  } catch (err) {
    ElMessage.error('保存失败！')
    console.error(err)
  }
}

// 敏感词相关
const wordList = ref([])
const newWord = ref('')
const newCategory = ref('高风险')

// 加载数据库中的敏感词
const getWordList = async () => {
  try {
    const res = await axios.get('/api/config/sensitive/words')
    // 字段映射：后端字段 → 前端展示字段
    wordList.value = res.data.data.map(item => ({
      id: item.id,
      word: item.word,
      risk: item.risk_level,
      creator: item.creator_id,
      time: item.created_at
    }))
  } catch (err) {
    console.error('加载敏感词失败', err)
  }
}

// 工作时间配置
const workTime = reactive({
  start: '09:30',
  end: '18:30'
})

// 加载工作时间配置
const getWorkTime = async () => {
  try {
    const res = await axios.get('/api/oa/work-time')
    if (res.data.status === 'success') {
      workTime.start = res.data.data.work_start_time
      workTime.end = res.data.data.work_end_time
    }
  } catch (err) {
    console.error('加载工作时间失败', err)
  }
}

// 保存工作时间配置
const saveWorkTime = async () => {
  try {
    await axios.post('/api/oa/work-time', {
      work_start_time: workTime.start,
      work_end_time: workTime.end
    })
    ElMessage.success('工作时间保存成功！非工作时间操作将被标记为异常。')
  } catch (err) {
    ElMessage.error('保存失败！')
    console.error(err)
  }
}

// 页面一打开就加载数据
onMounted(() => {
  getWordList()
  getWorkTime()
})

// 添加敏感词（对接后端数据库）
const addWord = async () => {
  if (!newWord.value.trim()) return ElMessage.warning('请输入敏感词！')

  try {
    await axios.post('/api/config/sensitive/words/add', {
      word: newWord.value.trim(),
      risk_level: newCategory.value
    })
    ElMessage.success('添加成功！')
    getWordList() // 刷新列表
    newWord.value = ''
  } catch (err) {
    ElMessage.error('添加失败！')
    console.error(err)
  }
}

// 🔥 修复3：删除敏感词（用ID而非索引，对接数据库）
const removeWord = async (id) => {
  try {
    await axios.delete(`/api/config/sensitive/words/delete/${id}`)
    ElMessage.success('删除成功！')
    getWordList() // 刷新列表
  } catch (err) {
    ElMessage.error('删除失败！')
    console.error(err)
  }
}

</script>

<style scoped>
.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: bold;
  color: #333;
}
.help-text {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

/* 渐变蓝色主按钮 */
.custom-btn {
  border: none;
  color: #fff;
  background-image: linear-gradient(30deg, #0400ff, #4ce3f7);
  border-radius: 20px;
  background-size: 100% auto;
  font-family: inherit;
  font-size: 14px;
  padding: 0.4em 1.2em;
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

@keyframes pulse512 {
  0% { box-shadow: 0 0 0 0 #05bada66; }
  70% { box-shadow: 0 0 0 10px rgb(0 0 0 / 0%); }
  100% { box-shadow: 0 0 0 0 rgb(0 0 0 / 0%); }
}

/* 自适应删除按钮 */
.del-button {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background-color: rgb(20, 20, 20);
  border: none;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.164);
  cursor: pointer;
  transition-duration: .3s;
  overflow: hidden;
  position: relative;
  margin: 0 auto;
}

.svgIcon {
  width: 10px;
  transition-duration: .3s;
}

.svgIcon path {
  fill: white;
}

.del-button:hover {
  width: 70px;
  border-radius: 20px;
  transition-duration: .3s;
  background-color: rgb(255, 69, 69);
  align-items: center;
}

.del-button:hover .svgIcon {
  width: 20px;
  transition-duration: .3s;
  transform: translateY(60%);
}

.del-button::before {
  position: absolute;
  top: -20px;
  content: "Delete";
  color: white;
  transition-duration: .3s;
  font-size: 2px;
}

.del-button:hover::before {
  font-size: 11px;
  opacity: 1;
  transform: translateY(24px);
  transition-duration: .3s;
}
</style>