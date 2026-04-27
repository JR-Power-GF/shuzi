<template>
  <div v-loading="loading">
    <h3 style="margin-bottom: 16px">教学概览</h3>

    <el-row :gutter="16" style="margin-bottom: 24px">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="我的课程" :value="data.my_active_courses" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="我的任务" :value="data.my_active_tasks" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="总提交数" :value="data.my_total_submissions" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="待评分" :value="data.my_pending_grades">
            <template #suffix>
              <el-tag v-if="data.my_pending_grades > 0" type="warning" size="small" style="margin-left: 8px">需处理</el-tag>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-bottom: 24px">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="迟交数" :value="data.my_late_submissions" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic
            v-if="data.my_avg_score !== null"
            title="平均分"
            :value="data.my_avg_score"
            :precision="1"
          />
          <div v-else>
            <div style="margin-bottom: 4px; color: #909399; font-size: 13px">平均分</div>
            <div style="font-size: 20px; font-weight: 600">--</div>
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
  my_active_courses: 0, my_active_tasks: 0, my_total_submissions: 0,
  my_late_submissions: 0, my_pending_grades: 0, my_avg_score: null,
  my_daily_submissions_last_7d: [],
})

onBeforeUnmount(() => {
  if (resizeHandler.value) window.removeEventListener('resize', resizeHandler.value)
})

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get('/dashboard/teacher')
    data.value = resp.data
    await nextTick()
    renderChart(data.value.my_daily_submissions_last_7d)
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
    series: [{ type: 'bar', data: dailyData.map(d => d.count), itemStyle: { color: '#67c23a' } }],
  })
  resizeHandler.value = () => chart.resize()
  window.addEventListener('resize', resizeHandler.value)
}
</script>
