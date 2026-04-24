<template>
  <div v-loading="loading">
    <h3>编辑任务</h3>
    <el-form v-if="task" :model="form" :rules="rules" ref="formRef" label-width="120px" style="max-width: 600px">
      <el-form-item label="任务标题" prop="title">
        <el-input v-model="form.title" />
      </el-form-item>
      <el-form-item label="任务描述">
        <el-input v-model="form.description" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="实验要求">
        <el-input v-model="form.requirements" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="关联课程">
        <el-select v-model="form.course_id" placeholder="选择课程（可选）" clearable>
          <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="截止时间" prop="deadline">
        <el-date-picker v-model="form.deadline" type="datetime" placeholder="选择截止时间" />
      </el-form-item>
      <el-form-item label="允许文件类型">
        <el-select v-model="form.allowed_file_types" multiple>
          <el-option v-for="ft in fileTypes" :key="ft" :label="ft" :value="ft" />
        </el-select>
      </el-form-item>
      <el-form-item label="最大文件大小(MB)">
        <el-input-number v-model="form.max_file_size_mb" :min="1" :max="100" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSubmit" :loading="saving">保存修改</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id

const task = ref(null)
const loading = ref(false)
const saving = ref(false)
const formRef = ref(null)
const fileTypes = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar', '.jpg', '.png', '.txt', '.csv']
const courses = ref([])

const form = reactive({ title: '', description: '', requirements: '', deadline: '', allowed_file_types: [], max_file_size_mb: 50, course_id: null })
const rules = {
  title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }],
  deadline: [{ required: true, message: '请选择截止时间', trigger: 'change' }],
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get(`/tasks/${taskId}`)
    task.value = resp.data
    Object.assign(form, {
      title: task.value.title,
      description: task.value.description || '',
      requirements: task.value.requirements || '',
      deadline: task.value.deadline,
      allowed_file_types: task.value.allowed_file_types || [],
      max_file_size_mb: task.value.max_file_size_mb || 50,
      course_id: task.value.course_id || null,
    })
    const courseResp = await api.get('/courses')
    courses.value = courseResp.data.filter(c => c.status === 'active')
  } catch { ElMessage.error('获取任务详情失败') }
  finally { loading.value = false }
})

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    await api.put(`/tasks/${taskId}`, {
      ...form,
      deadline: form.deadline instanceof Date ? form.deadline.toISOString() : form.deadline,
    })
    ElMessage.success('修改成功')
    router.push('/teacher/tasks')
  } catch (err) { ElMessage.error(err.response?.data?.detail || '修改失败') }
  finally { saving.value = false }
}
</script>
