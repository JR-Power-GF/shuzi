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
          <el-statistic title="班级数" :value="data.total_classes" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="课程（活跃/归档）" :value="data.total_active_courses" />
          <div style="color: #909399; font-size: 12px; margin-top: 4px">归档：{{ data.total_archived_courses }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="任务（活跃/归档）" :value="data.total_active_tasks" />
          <div style="color: #909399; font-size: 12px; margin-top: 4px">归档：{{ data.total_archived_tasks }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-bottom: 24px">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="总提交数" :value="data.total_submissions" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="待评分" :value="data.pending_grades">
            <template #suffix>
              <el-tag v-if="data.pending_grades > 0" type="warning" size="small" style="margin-left: 8px">需处理</el-tag>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="已评分" :value="data.graded" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="迟交数" :value="data.late_submissions" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-bottom: 24px">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic
            v-if="data.avg_score !== null"
            title="平均分"
            :value="data.avg_score"
            :precision="1"
          />
          <div v-else>
            <div style="margin-bottom: 4px; color: #909399; font-size: 13px">平均分</div>
            <div style="font-size: 20px; font-weight: 600">--</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div style="margin-bottom: 4px; color: #909399; font-size: 13px">最近截止日期</div>
          <div v-if="data.nearby_deadline" style="font-size: 14px; font-weight: 600">{{ data.nearby_deadline }}</div>
          <div v-else style="font-size: 14px; color: #c0c4cc">暂无</div>
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
const resizeHandler = ref(null)
const data = ref({
  total_users: 0, users_by_role: {}, total_classes: 0,
  total_active_courses: 0, total_archived_courses: 0,
  total_active_tasks: 0, total_archived_tasks: 0,
  total_submissions: 0, pending_grades: 0, graded: 0,
  late_submissions: 0, avg_score: null, nearby_deadline: null,
  daily_submissions_last_7d: [],
})

onBeforeUnmount(() => {
  if (resizeHandler.value) window.removeEventListener('resize', resizeHandler.value)
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
  resizeHandler.value = () => chart.resize()
  window.addEventListener('resize', resizeHandler.value)
}
</script>
