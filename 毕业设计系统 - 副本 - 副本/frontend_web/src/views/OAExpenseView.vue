<template>
  <div class="oa-expense-container">
    <el-card class="oa-card">
      <template #header>
        <div class="card-header">
          <h2>财务报销中心</h2>
          <el-button @click="$router.push('/oa')">返回 OA 主页</el-button>
        </div>
      </template>

      <el-form label-width="100px" style="max-width: 500px;">
        <el-form-item label="报销人">
          <el-input value="演示管理员" disabled />
        </el-form-item>
        <el-form-item label="报销金额">
          <el-input-number v-model="amount" :min="1" :step="100" />
        </el-form-item>
        <el-form-item label="发票附件">
           <el-upload
            class="upload-demo"
            action="#"
            :auto-upload="false"
          >
            <el-button type="primary">点击上传发票(模拟)</el-button>
            <template #tip>
              <div class="el-upload__tip">
                支持 jpg/png/pdf 文件，不超过 5MB (受防病毒策略保护)
              </div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-button type="success" @click="submitExpense">提交至财务系统</el-button>
        </el-form-item>
      </el-form>

    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const amount = ref(500)

const submitExpense = () => {
  ElMessage.success('报销单已加密传输至内部财务结算系统。')
}
</script>

<style scoped>
.oa-card {
  max-width: 800px;
  margin: 0 auto;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>