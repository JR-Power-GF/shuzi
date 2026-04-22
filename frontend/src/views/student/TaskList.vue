<template>
  <div>
    <h3 style="margin-bottom: 16px">我的任务</h3>
    <el-table :data="tasks" v-loading="loading" stripe>
      <el-table-column prop="title" label="任务标题" min-width="150" />
      <el-table-column prop="class_name" label="班级" width="150" />
      <el-table-column label="截止时间" width="170">
        <template #default="{ row }">{{ formatDate(row.deadline) }}</template>
      </el-table-column>
      <el-table-column label="成绩状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.grades_published ? 'success' : 'info'" size="small">
            {{ row.grades_published ? '已出分' : '未出分' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="$router.push(`/student/tasks/${row.id}`)">
            查看
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const tasks = ref([])
const loading = ref(false)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get('/tasks/my')
    tasks.value = resp.data
  } catch {
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
})
</script>
