<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" title="返回" :content="task?.title || '任务详情'" />
    <div v-if="task" style="margin-top: 20px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="任务标题">{{ task.title }}</el-descriptions-item>
        <el-descriptions-item label="班级">{{ task.class_name }}</el-descriptions-item>
        <el-descriptions-item label="截止时间">{{ formatDate(task.deadline) }}</el-descriptions-item>
        <el-descriptions-item label="允许文件类型">{{ task.allowed_file_types?.join(', ') }}</el-descriptions-item>
        <el-descriptions-item label="任务描述" :span="2">{{ task.description || '无' }}</el-descriptions-item>
        <el-descriptions-item label="实验要求" :span="2">{{ task.requirements || '无' }}</el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <h4>提交作业</h4>
      <FileUpload
        ref="uploadRef"
        :allowed-types="task.allowed_file_types || ['.pdf']"
        :max-size-m-b="task.max_file_size_mb || 50"
        @update:tokens="fileTokens = $event"
      />
      <el-button
        type="primary"
        style="margin-top: 16px"
        :loading="submitting"
        :disabled="fileTokens.length === 0"
        @click="handleSubmit"
      >
        提交作业
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'
import FileUpload from '../../components/FileUpload.vue'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id

const task = ref(null)
const loading = ref(false)
const submitting = ref(false)
const fileTokens = ref([])
const uploadRef = ref(null)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get(`/tasks/${taskId}`)
    task.value = resp.data
  } catch {
    ElMessage.error('获取任务详情失败')
  } finally {
    loading.value = false
  }
})

async function handleSubmit() {
  if (fileTokens.value.length === 0) {
    ElMessage.warning('请先上传文件')
    return
  }
  try {
    await ElMessageBox.confirm('确认提交作业？提交后可重新提交。', '确认')
  } catch {
    return
  }

  submitting.value = true
  try {
    const resp = await api.post(`/tasks/${taskId}/submissions`, {
      file_tokens: fileTokens.value,
    })
    ElMessage.success(`提交成功 (版本 ${resp.data.version})`)
    uploadRef.value?.clearFiles()
    fileTokens.value = []
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}
</script>
