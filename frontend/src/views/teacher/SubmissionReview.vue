<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" title="返回" content="提交列表" />

    <div style="margin-top: 20px; display: flex; gap: 12px; align-items: center">
      <el-tag v-if="task">
        {{ task.title }} — {{ task.class_name }}
      </el-tag>
      <el-button
        v-if="task && !task.grades_published"
        type="success"
        size="small"
        @click="handlePublish"
      >
        发布成绩
      </el-button>
      <el-button
        v-if="task && task.grades_published"
        type="warning"
        size="small"
        @click="handleUnpublish"
      >
        撤回发布
      </el-button>
    </div>

    <el-table :data="submissions" stripe style="margin-top: 16px">
      <el-table-column prop="student_name" label="学生" width="100" />
      <el-table-column prop="version" label="版本" width="70" />
      <el-table-column label="迟交" width="70">
        <template #default="{ row }">
          <el-tag v-if="row.is_late" type="warning" size="small">迟交</el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="提交时间" width="170">
        <template #default="{ row }">{{ formatDate(row.submitted_at) }}</template>
      </el-table-column>
      <el-table-column label="成绩" width="100">
        <template #default="{ row }">
          <span v-if="row.grade">{{ row.grade.score }} 分</span>
          <el-tag v-else type="info" size="small">未评分</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openGrading(row)">评分</el-button>
          <el-button size="small" text @click="downloadFile(row)">下载</el-button>
        </template>
      </el-table-column>
    </el-table>

    <GradingDialog
      v-model:visible="gradingVisible"
      :submission="gradingSubmission"
      :task-id="taskId"
      :late-penalty-percent="task?.late_penalty_percent"
      @graded="fetchSubmissions"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'
import GradingDialog from '../../components/GradingDialog.vue'

const route = useRoute()
const taskId = route.params.id

const task = ref(null)
const submissions = ref([])
const loading = ref(false)
const gradingVisible = ref(false)
const gradingSubmission = ref(null)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

async function fetchSubmissions() {
  loading.value = true
  try {
    const [taskResp, subsResp] = await Promise.all([
      api.get(`/tasks/${taskId}`),
      api.get(`/tasks/${taskId}/submissions`),
    ])
    task.value = taskResp.data
    submissions.value = subsResp.data
  } catch {
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchSubmissions)

function openGrading(submission) {
  gradingSubmission.value = submission
  gradingVisible.value = true
}

async function downloadFile(submission) {
  if (!submission.files?.length) {
    ElMessage.info('该提交无文件')
    return
  }
  const file = submission.files[0]
  window.open(`/api/files/${file.id}`, '_blank')
}

async function handlePublish() {
  try {
    await ElMessageBox.confirm('确认发布成绩？发布后学生可查看分数。', '确认发布')
    await api.post(`/tasks/${taskId}/grades/publish`)
    ElMessage.success('成绩已发布')
    await fetchSubmissions()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error('发布失败')
  }
}

async function handleUnpublish() {
  try {
    await ElMessageBox.confirm('确认撤回成绩发布？', '确认撤回')
    await api.post(`/tasks/${taskId}/grades/unpublish`)
    ElMessage.success('已撤回发布')
    await fetchSubmissions()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error('撤回失败')
  }
}
</script>
