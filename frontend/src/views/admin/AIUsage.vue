<template>
  <div>
    <h3 style="margin-bottom: 16px">AI 使用记录</h3>
    <el-table :data="usage.items" v-loading="loading" stripe>
      <el-table-column prop="user_id" label="用户ID" width="80" />
      <el-table-column prop="endpoint" label="功能" width="130" />
      <el-table-column prop="model" label="模型" width="120" />
      <el-table-column prop="prompt_tokens" label="输入 tokens" width="100" />
      <el-table-column prop="completion_tokens" label="输出 tokens" width="100" />
      <el-table-column prop="cost_microdollars" label="费用(μ$)" width="90" />
      <el-table-column prop="latency_ms" label="延迟(ms)" width="90" />
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
            {{ row.status === 'success' ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" min-width="150">
        <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const usage = reactive({ items: [], total: 0, budget_used: 0, budget_remaining: 0 })
const loading = ref(false)

async function fetchUsage() {
  loading.value = true
  try {
    const resp = await api.get('/ai/usage')
    Object.assign(usage, resp.data)
  } catch { ElMessage.error('获取使用记录失败') }
  finally { loading.value = false }
}

onMounted(fetchUsage)
</script>
