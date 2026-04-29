<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">我的任务</h3>
      <el-button type="primary" @click="$router.push('/teacher/tasks/create')">创建任务</el-button>
    </div>
    <el-table :data="tasks" v-loading="loading" stripe>
      <el-table-column prop="title" label="任务标题" min-width="150" />
      <el-table-column prop="class_name" label="班级" width="150" />
      <el-table-column label="截止时间" width="170">
        <template #default="{ row }">{{ formatDate(row.deadline) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">
            {{ row.status === 'active' ? '进行中' : '已归档' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="成绩" width="80">
        <template #default="{ row }">
          <el-tag :type="row.grades_published ? 'success' : 'warning'" size="small">
            {{ row.grades_published ? '已发布' : '未发布' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/teacher/tasks/${row.id}/submissions`)">
            查看提交
          </el-button>
          <el-button size="small" @click="$router.push(`/teacher/tasks/${row.id}/edit`)">编辑</el-button>
          <el-button v-if="row.status === 'active'" size="small" type="warning" @click="handleArchive(row)">归档</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const tasks = ref([])
const loading = ref(false)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

async function fetchTasks() {
  loading.value = true
  try {
    const resp = await api.get('/tasks/my')
    tasks.value = resp.data
  } catch { ElMessage.error('获取任务列表失败') }
  finally { loading.value = false }
}

async function handleArchive(task) {
  try {
    await ElMessageBox.confirm(`确认归档任务 "${task.title}"？`, '归档')
    await api.post(`/tasks/${task.id}/archive`)
    ElMessage.success('已归档')
    await fetchTasks()
  } catch (err) { if (err !== 'cancel') ElMessage.error('归档失败') }
}

async function handleDelete(task) {
  try {
    await ElMessageBox.confirm(`确认删除任务 "${task.title}"？已有提交的任务无法删除。`, '删除任务')
    await api.delete(`/tasks/${task.id}`)
    ElMessage.success('已删除')
    await fetchTasks()
  } catch (err) { if (err !== 'cancel') ElMessage.error(err.response?.data?.detail || '删除失败') }
}

onMounted(fetchTasks)
</script>
