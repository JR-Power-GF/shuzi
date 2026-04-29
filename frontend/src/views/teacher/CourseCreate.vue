<template>
  <div>
    <h3>创建课程</h3>
    <el-form :model="form" :rules="rules" ref="formRef" label-width="100px" style="max-width: 500px">
      <el-form-item label="课程名称" prop="name">
        <el-input v-model="form.name" placeholder="如：Python程序设计" />
      </el-form-item>
      <el-form-item label="课程描述">
        <el-input v-model="form.description" type="textarea" :rows="3" placeholder="课程简介（可选）" />
      </el-form-item>
      <el-form-item label="学期" prop="semester">
        <el-select v-model="form.semester" placeholder="选择学期">
          <el-option label="2026-2027-1" value="2026-2027-1" />
          <el-option label="2026-2027-2" value="2026-2027-2" />
          <el-option label="2025-2026-1" value="2025-2026-1" />
          <el-option label="2025-2026-2" value="2025-2026-2" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSubmit" :loading="loading">创建课程</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({ name: '', description: '', semester: '' })
const rules = {
  name: [{ required: true, message: '请输入课程名称', trigger: 'blur' }],
  semester: [{ required: true, message: '请选择学期', trigger: 'change' }],
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await api.post('/courses', form)
    ElMessage.success('课程创建成功')
    router.push('/teacher/courses')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '创建失败')
  } finally {
    loading.value = false
  }
}
</script>
