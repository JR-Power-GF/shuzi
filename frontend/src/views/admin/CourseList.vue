<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">课程管理</h3>
    </div>
    <div style="margin-bottom: 16px; display: flex; gap: 12px">
      <el-select v-model="semesterFilter" placeholder="筛选学期" clearable style="width: 160px" @change="fetchCourses">
        <el-option label="2026-2027-1" value="2026-2027-1" />
        <el-option label="2026-2027-2" value="2026-2027-2" />
        <el-option label="2025-2026-1" value="2025-2026-1" />
        <el-option label="2025-2026-2" value="2025-2026-2" />
      </el-select>
      <el-select v-model="statusFilter" placeholder="筛选状态" clearable style="width: 120px" @change="fetchCourses">
        <el-option label="进行中" value="active" />
        <el-option label="已归档" value="archived" />
      </el-select>
    </div>
    <el-table :data="courses" v-loading="loading" stripe>
      <el-table-column prop="name" label="课程名称" min-width="150" />
      <el-table-column prop="semester" label="学期" width="130" />
      <el-table-column prop="teacher_name" label="教师" width="100" />
      <el-table-column prop="task_count" label="任务数" width="80" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
            {{ row.status === 'active' ? '进行中' : '已归档' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const courses = ref([])
const loading = ref(false)
const semesterFilter = ref('')
const statusFilter = ref('')

async function fetchCourses() {
  loading.value = true
  try {
    const params = {}
    if (semesterFilter.value) params.semester = semesterFilter.value
    if (statusFilter.value) params.status = statusFilter.value
    const resp = await api.get('/courses', { params })
    courses.value = resp.data
  } catch { ElMessage.error('获取课程列表失败') }
  finally { loading.value = false }
}

onMounted(fetchCourses)
</script>
