<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" title="返回" :content="course?.name || '课程详情'" />
    <div v-if="course" style="margin-top: 20px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="课程名称">{{ course.name }}</el-descriptions-item>
        <el-descriptions-item label="学期">{{ course.semester }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="course.status === 'active' ? 'success' : 'info'">
            {{ course.status === 'active' ? '进行中' : '已归档' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="任务数">{{ course.task_count }}</el-descriptions-item>
        <el-descriptions-item label="课程描述" :span="2">{{ course.description || '无' }}</el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
        <h4 style="margin: 0">课程任务</h4>
        <el-button type="primary" size="small" @click="$router.push('/teacher/tasks/create')">添加任务</el-button>
      </div>
      <el-table :data="course.tasks" stripe>
        <el-table-column prop="title" label="任务标题" min-width="150" />
        <el-table-column prop="class_name" label="班级" width="120" />
        <el-table-column label="截止时间" width="170">
          <template #default="{ row }">{{ formatDate(row.deadline) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '进行中' : '已归档' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'

const route = useRoute()
const courseId = route.params.id

const course = ref(null)
const loading = ref(false)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get(`/courses/${courseId}`)
    course.value = resp.data
  } catch {
    ElMessage.error('获取课程详情失败')
  } finally {
    loading.value = false
  }
})
</script>
