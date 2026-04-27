<template>
  <div v-loading="loading">
    <h3 style="margin-bottom: 16px">系统概览</h3>

    <el-row :gutter="16" style="margin-bottom: 24px">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="用户总数" :value="data.total_users" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="活跃课程" :value="data.total_active_courses" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="活跃任务" :value="data.total_active_tasks" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="总提交数" :value="data.total_submissions" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-bottom: 24px">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="迟交数" :value="data.late_submissions" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="待评分" :value="data.pending_grades" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic
            title="平均分"
            :value="data.avg_score !== null ? data.avg_score : '-'"
            :precision="1"
          />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="margin-bottom: 8px; color: #909399; font-size: 13px">用户分布</div>
          <div v-for="(count, role) in data.users_by_role" :key="role" style="font-size: 14px; margin-bottom: 4px">
            {{ roleLabel(role) }}：{{ count }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover">
      <template #header><span>近 7 天提交趋势</span></template>
      <div ref="chartRef" style="height: 300px" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const loading = ref(false)
const chartRef = ref(null)
const data = ref({
  total_users: 0, users_by_role: {}, total_active_courses: 0,
  total_active_tasks: 0, total_submissions: 0, late_submissions: 0,
  pending_grades: 0, avg_score: null, daily_submissions_last_7d: [],
})

function roleLabel(role) {
  const map = { admin: '管理员', teacher: '教师', student: '学生' }
  return map[role] || role
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get('/dashboard/admin')
    data.value = resp.data
    await nextTick()
    renderChart(data.value.daily_submissions_last_7d)
  } catch {
    ElMessage.error('获取统计数据失败')
  } finally {
    loading.value = false
  }
})

function renderChart(dailyData) {
  if (!chartRef.value || !window.echarts) return
  const chart = window.echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: dailyData.map(d => d.date) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ type: 'bar', data: dailyData.map(d => d.count), itemStyle: { color: '#409eff' } }],
  })
  const onResize = () => chart.resize()
  window.addEventListener('resize', onResize)
  onBeforeUnmount(() => window.removeEventListener('resize', onResize))
}
</script>
