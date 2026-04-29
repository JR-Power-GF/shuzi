<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">课程管理</h3>
      <el-button type="primary" @click="$router.push('/teacher/courses/create')">创建课程</el-button>
    </div>
    <el-table :data="courses" v-loading="loading" stripe>
      <el-table-column prop="name" label="课程名称" min-width="150" />
      <el-table-column prop="semester" label="学期" width="130" />
      <el-table-column prop="task_count" label="任务数" width="80" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">
            {{ row.status === 'active' ? '进行中' : '已归档' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/teacher/courses/${row.id}`)">查看</el-button>
          <el-button v-if="row.status === 'active'" size="small" type="warning" @click="handleArchive(row)">归档</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const courses = ref([])
const loading = ref(false)

async function fetchCourses() {
  loading.value = true
  try {
    const resp = await api.get('/courses')
    courses.value = resp.data
  } catch { ElMessage.error('获取课程列表失败') }
  finally { loading.value = false }
}

async function handleArchive(course) {
  try {
    await ElMessageBox.confirm(`确认归档课程 "${course.name}"？归档后学生将看不到该课程及任务。`, '归档课程')
    await api.post(`/courses/${course.id}/archive`)
    ElMessage.success('已归档')
    await fetchCourses()
  } catch (err) { if (err !== 'cancel') ElMessage.error('归档失败') }
}

onMounted(fetchCourses)
</script>
