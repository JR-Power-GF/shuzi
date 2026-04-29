<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" title="返回" content="班级花名册" />
    <div v-if="cls" style="margin-top: 16px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="班级名称">{{ cls.name }}</el-descriptions-item>
        <el-descriptions-item label="学期">{{ cls.semester }}</el-descriptions-item>
        <el-descriptions-item label="学生数">{{ students.length }}</el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <h4>学生列表</h4>
      <el-table :data="students" stripe>
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="real_name" label="姓名" />
      </el-table>

      <el-divider />

      <h4>添加学生</h4>
      <div style="display: flex; gap: 12px; align-items: center">
        <el-input v-model="newStudentIds" placeholder="输入学生ID，多个用逗号分隔" style="max-width: 400px" />
        <el-button type="primary" @click="handleEnroll" :loading="enrolling">添加</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'

const route = useRoute()
const classId = route.params.id

const cls = ref(null)
const students = ref([])
const loading = ref(false)
const newStudentIds = ref('')
const enrolling = ref(false)

async function fetchData() {
  loading.value = true
  try {
    const [clsResp, stuResp] = await Promise.all([
      api.get(`/classes/${classId}/students`),
      api.get('/classes').catch(() => ({ data: { items: [] } })),
    ])
    students.value = clsResp.data
    const allClasses = stuResp.data.items || []
    cls.value = allClasses.find(c => c.id === parseInt(classId)) || { name: '班级', semester: '' }
  } catch { ElMessage.error('获取数据失败') }
  finally { loading.value = false }
}

async function handleEnroll() {
  const ids = newStudentIds.value.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
  if (ids.length === 0) { ElMessage.warning('请输入有效的学生ID'); return }
  enrolling.value = true
  try {
    await api.post(`/classes/${classId}/students`, { student_ids: ids })
    ElMessage.success('添加成功')
    newStudentIds.value = ''
    await fetchData()
  } catch (err) { ElMessage.error(err.response?.data?.detail || '添加失败') }
  finally { enrolling.value = false }
}

onMounted(fetchData)
</script>
