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

      <el-divider />

      <div style="display: flex; align-items: center; justify-content: space-between">
        <h4>任务问答助手</h4>
        <el-button size="small" @click="showQAPanel = !showQAPanel">
          {{ showQAPanel ? '收起' : '展开' }}
        </el-button>
      </div>

      <div v-if="showQAPanel" style="margin-top: 12px">
        <div
          v-for="(msg, idx) in qaMessages"
          :key="idx"
          :style="{
            display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: '12px',
          }"
        >
          <div
            :style="{
              maxWidth: '80%', padding: '10px 14px', borderRadius: '8px',
              backgroundColor: msg.role === 'user' ? '#409eff' : '#f4f4f5',
              color: msg.role === 'user' ? '#fff' : '#303133',
            }"
          >
            <div style="white-space: pre-wrap">{{ msg.content }}</div>
            <div v-if="msg.role === 'assistant' && msg.usageLogId" style="margin-top: 8px; text-align: right">
              <el-button-group>
                <el-button
                  size="small"
                  :type="msg.feedback === 1 ? 'primary' : 'default'"
                  @click="submitQAFeedback(idx, 1)"
                >
                  有用
                </el-button>
                <el-button
                  size="small"
                  :type="msg.feedback === -1 ? 'danger' : 'default'"
                  @click="submitQAFeedback(idx, -1)"
                >
                  待改进
                </el-button>
              </el-button-group>
            </div>
          </div>
        </div>

        <div style="display: flex; gap: 8px; margin-top: 8px">
          <el-input
            v-model="qaQuestion"
            placeholder="输入你关于这个任务的问题..."
            @keyup.enter="askQuestion"
            :disabled="qaLoading"
          />
          <el-button type="primary" @click="askQuestion" :loading="qaLoading" :disabled="!qaQuestion.trim()">
            提问
          </el-button>
        </div>
      </div>
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
const showQAPanel = ref(false)
const qaQuestion = ref('')
const qaLoading = ref(false)
const qaMessages = ref([])

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

async function askQuestion() {
  const question = qaQuestion.value.trim()
  if (!question) return

  qaMessages.value.push({ role: 'user', content: question })
  qaQuestion.value = ''
  qaLoading.value = true

  try {
    const resp = await api.post(`/tasks/${taskId}/qa`, { question })
    qaMessages.value.push({
      role: 'assistant',
      content: resp.data.answer,
      usageLogId: resp.data.usage_log_id,
      feedback: 0,
    })
  } catch (err) {
    if (err.response?.status === 429) {
      qaMessages.value.push({ role: 'assistant', content: '今日 AI 调用额度已用完，请明天再试。', usageLogId: null, feedback: 0 })
    } else if (err.response?.status === 502) {
      qaMessages.value.push({ role: 'assistant', content: 'AI 服务暂时不可用，请稍后再试。', usageLogId: null, feedback: 0 })
    } else {
      qaMessages.value.push({ role: 'assistant', content: err.response?.data?.detail || '问答失败，请重试。', usageLogId: null, feedback: 0 })
    }
  } finally {
    qaLoading.value = false
  }
}

async function submitQAFeedback(messageIndex, rating) {
  const msg = qaMessages.value[messageIndex]
  if (!msg?.usageLogId) return
  try {
    await api.post('/ai/feedback', { ai_usage_log_id: msg.usageLogId, rating })
    msg.feedback = rating
    ElMessage.success('感谢您的反馈')
  } catch {
    ElMessage.error('反馈提交失败')
  }
}
</script>
