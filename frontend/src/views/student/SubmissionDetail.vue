<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" title="返回" content="提交详情" />

    <div v-if="submission" style="margin-top: 20px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="版本">
          <el-tag size="large" type="primary">v{{ submission.version }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ formatDate(submission.submitted_at) }}</el-descriptions-item>
        <el-descriptions-item label="迟交">
          <el-tag v-if="submission.is_late" type="warning" size="small">迟交</el-tag>
          <span v-else>否</span>
        </el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <h4>提交文件</h4>
      <el-table :data="submission.files" stripe>
        <el-table-column prop="file_name" label="文件名" />
        <el-table-column label="大小" width="120">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" text @click="downloadFile(row)">下载</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-divider />

      <h4>成绩</h4>
      <div v-if="submission.grade">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="分数">
            <span style="font-size: 20px; font-weight: bold; color: #409eff">
              {{ submission.grade.score }} 分
            </span>
          </el-descriptions-item>
          <el-descriptions-item v-if="submission.grade.penalty_applied" label="迟交扣分">
            <span style="color: #e6a23c">-{{ submission.grade.penalty_applied }} 分</span>
          </el-descriptions-item>
          <el-descriptions-item label="评语" :span="2">
            {{ submission.grade.feedback || '无' }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <el-alert v-else type="info" :closable="false" description="成绩尚未发布，请等待教师评分并发布" />

      <el-divider />

      <div style="text-align: center">
        <el-button type="primary" @click="$router.back()">返回任务</el-button>
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
const submissionId = route.params.id

const submission = ref(null)
const loading = ref(false)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function downloadFile(file) {
  window.open(`/api/files/${file.id}`, '_blank')
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get(`/submissions/${submissionId}`)
    submission.value = resp.data
  } catch {
    ElMessage.error('获取提交详情失败')
  } finally {
    loading.value = false
  }
})
</script>
