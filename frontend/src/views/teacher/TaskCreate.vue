<template>
  <div>
    <h3>创建任务</h3>
    <el-form :model="form" :rules="rules" ref="formRef" label-width="120px" style="max-width: 600px">
      <el-form-item label="任务标题" prop="title">
        <el-input v-model="form.title" />
      </el-form-item>
      <el-form-item label="任务描述">
        <div style="width: 100%">
          <div style="margin-bottom: 8px">
            <el-button
              type="primary"
              plain
              size="small"
              @click="generateDescription"
              :loading="generating"
              :disabled="!form.title"
            >
              AI 生成描述
            </el-button>
            <span v-if="!form.title" style="color: #909399; font-size: 12px; margin-left: 8px">
              请先输入任务标题
            </span>
          </div>
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </div>
      </el-form-item>
      <el-form-item label="实验要求">
        <el-input v-model="form.requirements" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="选择班级" prop="class_id">
        <el-select v-model="form.class_id" placeholder="请选择班级">
          <el-option v-for="cls in classes" :key="cls.id" :label="cls.name" :value="cls.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关联课程">
        <el-select v-model="form.course_id" placeholder="选择课程（可选）" clearable>
          <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="截止时间" prop="deadline">
        <el-date-picker v-model="form.deadline" type="datetime" placeholder="选择截止时间" />
      </el-form-item>
      <el-form-item label="允许文件类型" prop="allowed_file_types">
        <el-select v-model="form.allowed_file_types" multiple placeholder="选择文件类型">
          <el-option v-for="ft in fileTypes" :key="ft" :label="ft" :value="ft" />
        </el-select>
      </el-form-item>
      <el-form-item label="最大文件大小(MB)">
        <el-input-number v-model="form.max_file_size_mb" :min="1" :max="100" />
      </el-form-item>
      <el-form-item label="允许迟交">
        <el-switch v-model="form.allow_late_submission" />
      </el-form-item>
      <el-form-item v-if="form.allow_late_submission" label="迟交扣分比例(%)">
        <el-input-number v-model="form.late_penalty_percent" :min="0" :max="100" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSubmit" :loading="loading">创建任务</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>
    <el-dialog v-model="showAIDialog" title="AI 生成的任务描述" width="700px" :close-on-click-modal="false">
      <el-input
        v-model="generatedDescription"
        type="textarea"
        :rows="15"
        placeholder="AI 正在生成..."
      />
      <div style="margin-top: 16px; display: flex; align-items: center; justify-content: space-between">
        <div>
          <span style="color: #909399; font-size: 13px">对生成结果满意吗？</span>
          <el-button-group style="margin-left: 8px">
            <el-button
              size="small"
              :type="aiFeedback === 1 ? 'primary' : 'default'"
              @click="submitAIFeedback(1)"
            >
              有用
            </el-button>
            <el-button
              size="small"
              :type="aiFeedback === -1 ? 'danger' : 'default'"
              @click="submitAIFeedback(-1)"
            >
              待改进
            </el-button>
          </el-button-group>
        </div>
        <div>
          <el-button @click="showAIDialog = false">取消</el-button>
          <el-button type="primary" @click="confirmAIDescription">确认使用</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)
const generating = ref(false)
const showAIDialog = ref(false)
const generatedDescription = ref('')
const usageLogId = ref(null)
const aiFeedback = ref(0)
const classes = ref([])
const courses = ref([])

const fileTypes = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar', '.jpg', '.png', '.txt', '.csv']

const form = reactive({
  title: '',
  description: '',
  requirements: '',
  class_id: '',
  course_id: null,
  deadline: '',
  allowed_file_types: ['.pdf', '.docx'],
  max_file_size_mb: 50,
  allow_late_submission: false,
  late_penalty_percent: null,
})

const rules = {
  title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }],
  class_id: [{ required: true, message: '请选择班级', trigger: 'change' }],
  deadline: [{ required: true, message: '请选择截止时间', trigger: 'change' }],
  allowed_file_types: [{ required: true, message: '请选择文件类型', trigger: 'change', type: 'array', min: 1 }],
}

onMounted(async () => {
  try {
    const resp = await api.get('/classes/my')
    classes.value = resp.data
    const courseResp = await api.get('/courses')
    courses.value = courseResp.data.filter(c => c.status === 'active')
  } catch {
    ElMessage.error('获取班级列表失败')
  }
})

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await api.post('/tasks', {
      ...form,
      deadline: form.deadline.toISOString(),
    })
    ElMessage.success('任务创建成功')
    router.push('/teacher/tasks')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '创建失败')
  } finally {
    loading.value = false
  }
}

async function generateDescription() {
  generating.value = true
  try {
    const courseName = form.course_id
      ? courses.value.find(c => c.id === form.course_id)?.name || '实训课程'
      : '实训课程'

    const resp = await api.post('/tasks/generate-description', {
      title: form.title,
      course_name: courseName,
      language: '中文',
    })

    generatedDescription.value = resp.data.description
    usageLogId.value = resp.data.usage_log_id
    aiFeedback.value = 0
    showAIDialog.value = true
  } catch (err) {
    if (err.response?.status === 429) {
      ElMessage.error('今日 AI 调用额度已用完')
    } else if (err.response?.status === 502) {
      ElMessage.error('AI 服务暂时不可用，请稍后再试')
    } else {
      ElMessage.error(err.response?.data?.detail || 'AI 生成失败')
    }
  } finally {
    generating.value = false
  }
}

function confirmAIDescription() {
  form.description = generatedDescription.value
  showAIDialog.value = false
  ElMessage.success('已填入 AI 生成的描述，可继续编辑')
}

async function submitAIFeedback(rating) {
  if (!usageLogId.value) return
  try {
    await api.post('/ai/feedback', {
      ai_usage_log_id: usageLogId.value,
      rating: rating,
    })
    aiFeedback.value = rating
    ElMessage.success('感谢您的反馈')
  } catch {
    ElMessage.error('反馈提交失败')
  }
}
</script>
