<template>
  <div v-loading="loading">
    <h3 style="margin-bottom: 16px">课程统计</h3>

    <el-table :data="data.courses" stripe border style="width: 100%">
      <el-table-column prop="course_name" label="课程名称" min-width="160" />
      <el-table-column prop="teacher_name" label="授课教师" width="120" />
      <el-table-column prop="task_count" label="任务数" width="90" align="center" />
      <el-table-column prop="submission_count" label="提交数" width="90" align="center" />
      <el-table-column prop="pending_grade_count" label="待评分" width="90" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.pending_grade_count > 0" type="warning" size="small">{{ row.pending_grade_count }}</el-tag>
          <span v-else>{{ row.pending_grade_count }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="graded_count" label="已评分" width="90" align="center" />
      <el-table-column label="平均分" width="100" align="center">
        <template #default="{ row }">
          {{ row.average_score !== null ? row.average_score.toFixed(1) : '--' }}
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const loading = ref(false)
const data = ref({ courses: [] })

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get('/dashboard/courses')
    data.value = resp.data
  } catch {
    ElMessage.error('获取课程统计失败')
  } finally {
    loading.value = false
  }
})
</script>
