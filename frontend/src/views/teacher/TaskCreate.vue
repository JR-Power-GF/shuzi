<template>
  <div>
    <h3>创建任务</h3>
    <el-form :model="form" :rules="rules" ref="formRef" label-width="120px" style="max-width: 600px">
      <el-form-item label="任务标题" prop="title">
        <el-input v-model="form.title" />
      </el-form-item>
      <el-form-item label="任务描述">
        <el-input v-model="form.description" type="textarea" :rows="3" />
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
</script>
