<template>
  <div>
    <h3 style="margin-bottom: 16px">AI 反馈</h3>
    <el-descriptions :column="2" border style="margin-bottom: 16px">
      <el-descriptions-item label="正面评价">{{ summary.positive_count }}</el-descriptions-item>
      <el-descriptions-item label="负面评价">{{ summary.negative_count }}</el-descriptions-item>
    </el-descriptions>
    <h4>近期负面反馈</h4>
    <el-table :data="summary.recent_negative" v-loading="loading" stripe>
      <el-table-column prop="comment" label="评论" min-width="200" />
      <el-table-column prop="created_at" label="时间" width="170">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const summary = reactive({ positive_count: 0, negative_count: 0, recent_negative: [] })
const loading = ref(false)

async function fetchSummary() {
  loading.value = true
  try {
    const resp = await api.get('/ai/stats/feedback')
    Object.assign(summary, resp.data)
  } catch { ElMessage.error('获取反馈失败') }
  finally { loading.value = false }
}

onMounted(fetchSummary)
</script>
