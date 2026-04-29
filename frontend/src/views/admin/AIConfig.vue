<template>
  <div>
    <h3 style="margin-bottom: 16px">AI 配置</h3>
    <el-card v-loading="loading">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="当前模型">{{ config.model }}</el-descriptions-item>
        <el-descriptions-item label="API 密钥">
          <el-tag :type="config.is_configured ? 'success' : 'danger'" size="small">
            {{ config.is_configured ? '已配置' : '未配置' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="管理员预算">{{ config.budget_admin?.toLocaleString() }} tokens</el-descriptions-item>
        <el-descriptions-item label="教师预算">{{ config.budget_teacher?.toLocaleString() }} tokens</el-descriptions-item>
        <el-descriptions-item label="学生预算">{{ config.budget_student?.toLocaleString() }} tokens</el-descriptions-item>
      </el-descriptions>
      <el-divider />
      <el-form :model="form" label-width="100px" style="max-width: 400px">
        <el-form-item label="模型">
          <el-input v-model="form.model" />
        </el-form-item>
        <el-form-item label="管理员预算">
          <el-input-number v-model="form.budget_admin" :min="0" :step="10000" />
        </el-form-item>
        <el-form-item label="教师预算">
          <el-input-number v-model="form.budget_teacher" :min="0" :step="10000" />
        </el-form-item>
        <el-form-item label="学生预算">
          <el-input-number v-model="form.budget_student" :min="0" :step="10000" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSave" :loading="saving">保存配置</el-button>
          <el-button @click="handleTest" :loading="testing" type="success">测试调用</el-button>
        </el-form-item>
      </el-form>
      <el-alert v-if="testResult" type="success" :title="'测试成功'" :description="testResult" show-icon style="margin-top: 16px" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const config = ref({})
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref('')

const form = reactive({ model: '', budget_admin: 500000, budget_teacher: 200000, budget_student: 50000 })

async function fetchConfig() {
  loading.value = true
  try {
    const resp = await api.get('/ai/config')
    config.value = resp.data
    Object.assign(form, resp.data)
  } catch { ElMessage.error('获取配置失败') }
  finally { loading.value = false }
}

async function handleSave() {
  saving.value = true
  try {
    await api.put('/ai/config', form)
    ElMessage.success('配置已保存')
    await fetchConfig()
  } catch (err) { ElMessage.error(err.response?.data?.detail || '保存失败') }
  finally { saving.value = false }
}

async function handleTest() {
  testing.value = true
  testResult.value = ''
  try {
    const resp = await api.post('/ai/test')
    testResult.value = `回复: ${resp.data.text} (tokens: ${resp.data.prompt_tokens}/${resp.data.completion_tokens})`
  } catch (err) { ElMessage.error(err.response?.data?.detail || '测试失败') }
  finally { testing.value = false }
}

onMounted(fetchConfig)
</script>
