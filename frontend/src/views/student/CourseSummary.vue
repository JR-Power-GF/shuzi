<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" title="返回" :content="courseName || '实训总结'" />
    <div style="margin-top: 20px">
      <div v-if="!generated && !savedSummary" style="text-align: center; padding: 60px">
        <p style="color: #909399; margin-bottom: 20px">
          点击下方按钮，AI 将根据你的课程提交记录生成实训总结初稿
        </p>
        <el-button type="primary" size="large" @click="generateSummary" :loading="generating">
          生成实训总结
        </el-button>
      </div>

      <div v-else>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
          <span style="font-size: 14px; color: #909399">
            {{ generated ? 'AI 生成的初稿，你可以自由修改后保存' : '已保存的总结' }}
          </span>
          <el-button v-if="savedSummary" size="small" @click="regenerate" :loading="generating">
            重新生成
          </el-button>
        </div>
        <el-input
          v-model="summaryContent"
          type="textarea"
          :rows="15"
          placeholder="总结内容..."
        />
        <div style="margin-top: 16px; display: flex; gap: 12px">
          <el-button @click="saveSummary('draft')" :loading="saving">保存草稿</el-button>
          <el-button type="primary" @click="saveSummary('submitted')" :loading="saving">提交总结</el-button>
        </div>
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
const courseId = route.params.id

const courseName = ref('')
const loading = ref(false)
const generating = ref(false)
const saving = ref(false)
const generated = ref(false)
const savedSummary = ref(null)
const summaryContent = ref('')

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get(`/courses/${courseId}/summary`)
    savedSummary.value = resp.data
    summaryContent.value = resp.data.content
  } catch (err) {
    if (err.response?.status !== 404) {
      ElMessage.error('获取总结失败')
    }
  } finally {
    loading.value = false
  }

  try {
    const resp = await api.get('/courses')
    const course = resp.data.find(c => c.id === Number(courseId))
    if (course) courseName.value = course.name
  } catch {}
})

async function generateSummary() {
  generating.value = true
  try {
    const resp = await api.post(`/courses/${courseId}/generate-summary`)
    summaryContent.value = resp.data.content
    generated.value = true
  } catch (err) {
    if (err.response?.status === 429) {
      ElMessage.error('今日 AI 调用额度已用完，请明天再试')
    } else if (err.response?.status === 502) {
      ElMessage.error('AI 服务暂时不可用，请稍后再试')
    } else {
      ElMessage.error(err.response?.data?.detail || '生成失败')
    }
  } finally {
    generating.value = false
  }
}

async function regenerate() {
  generated.value = false
  savedSummary.value = null
  await generateSummary()
}

async function saveSummary(status) {
  if (!summaryContent.value.trim()) {
    ElMessage.warning('总结内容不能为空')
    return
  }
  saving.value = true
  try {
    const resp = await api.put(`/courses/${courseId}/summary`, {
      content: summaryContent.value,
      status,
    })
    savedSummary.value = resp.data
    generated.value = false
    ElMessage.success(status === 'submitted' ? '总结已提交' : '草稿已保存')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>
