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
      <el-button
        v-if="submissions.length > 0"
        type="primary"
        size="small"
        @click="showBulkGrade"
      >
        批量评分
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

    <el-dialog v-model="bulkVisible" title="批量评分" width="400px">
      <el-form label-width="80px">
        <el-form-item label="分数">
          <el-input-number v-model="bulkScore" :min="0" :max="100" :precision="1" />
          <span style="margin-left: 8px; color: #909399">/ 100</span>
        </el-form-item>
      </el-form>
      <p style="color: #909399; font-size: 13px">
        将为所有未评分的提交（{{ ungradedCount }} 个）设置相同分数，迟交扣分会自动计算。
      </p>
      <template #footer>
        <el-button @click="bulkVisible = false">取消</el-button>
        <el-button type="primary" :loading="bulkLoading" @click="handleBulkGrade">确认批量评分</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
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

const bulkVisible = ref(false)
const bulkScore = ref(80)
const bulkLoading = ref(false)

const ungradedCount = computed(() => submissions.value.filter(s => !s.grade).length)

function showBulkGrade() {
  bulkScore.value = 80
  bulkVisible.value = true
}

async function handleBulkGrade() {
  const ungraded = submissions.value.filter(s => !s.grade)
  if (ungraded.length === 0) { ElMessage.info('没有未评分的提交'); return }
  bulkLoading.value = true
  try {
    await api.post(`/tasks/${taskId}/grades/bulk`, {
      grades: ungraded.map(s => ({ submission_id: s.id, score: bulkScore.value })),
    })
    ElMessage.success(`已为 ${ungraded.length} 个提交评分`)
    bulkVisible.value = false
    await fetchSubmissions()
  } catch (err) { ElMessage.error(err.response?.data?.detail || '批量评分失败') }
  finally { bulkLoading.value = false }
}

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
