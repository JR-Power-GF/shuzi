<template>
  <div v-loading="loading">
    <h3 style="margin-bottom: 16px">我的课程</h3>
    <div v-if="courses.length === 0 && !loading" style="text-align: center; padding: 40px; color: #909399">
      暂无课程，请等待教师创建课程并分配任务
    </div>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px">
      <el-card v-for="course in courses" :key="course.id" shadow="hover">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <span style="font-size: 16px; font-weight: bold">{{ course.name }}</span>
            <el-tag size="small">{{ course.semester }}</el-tag>
          </div>
        </template>
        <p style="color: #606266; margin: 0 0 12px">{{ course.description || '暂无描述' }}</p>
        <p style="color: #909399; font-size: 13px; margin: 0 0 12px">教师：{{ course.teacher_name }}</p>
        <el-progress
          :percentage="course.task_count ? Math.round(course.submitted_count / course.task_count * 100) : 0"
          :format="() => `${course.submitted_count}/${course.task_count}`"
        />
        <div style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center">
          <span v-if="course.nearest_deadline" style="color: #e6a23c; font-size: 13px">
            最近截止：{{ formatDate(course.nearest_deadline) }}
          </span>
          <span v-else style="color: #909399; font-size: 13px">无待办任务</span>
          <el-tag v-if="course.graded_count > 0" type="success" size="small">
            已出分 {{ course.graded_count }}
          </el-tag>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const courses = ref([])
const loading = ref(false)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get('/courses/my')
    courses.value = resp.data
  } catch {
    ElMessage.error('获取课程列表失败')
  } finally {
    loading.value = false
  }
})
</script>
