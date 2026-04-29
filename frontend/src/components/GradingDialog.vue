<template>
  <el-dialog :model-value="visible" title="评分" width="450px" @close="handleClose">
    <el-form :model="form" label-width="80px">
      <el-form-item label="分数">
        <el-input-number v-model="form.score" :min="0" :max="100" :precision="1" />
        <span style="margin-left: 8px; color: #909399">/ 100</span>
      </el-form-item>
      <el-form-item v-if="penaltyInfo" label="迟交扣分">
        <span style="color: #e6a23c">-{{ penaltyInfo }} 分</span>
      </el-form-item>
      <el-form-item label="评语">
        <el-input v-model="form.feedback" type="textarea" :rows="3" placeholder="输入评语（可选）" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSave">保存评分</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const props = defineProps({
  visible: Boolean,
  submission: Object,
  taskId: [String, Number],
  latePenaltyPercent: { type: Number, default: null },
})

const emit = defineEmits(['update:visible', 'graded'])
const loading = ref(false)

const form = reactive({ score: 0, feedback: '' })

watch(() => props.visible, (val) => {
  if (val) {
    form.score = 0
    form.feedback = ''
  }
})

const penaltyInfo = computed(() => {
  if (!props.submission?.is_late || !props.latePenaltyPercent) return null
  return (form.score * props.latePenaltyPercent / 100).toFixed(1)
})

function handleClose() {
  emit('update:visible', false)
}

async function handleSave() {
  loading.value = true
  try {
    await api.post(`/tasks/${props.taskId}/grades`, {
      submission_id: props.submission.id,
      score: form.score,
      feedback: form.feedback || null,
    })
    ElMessage.success('评分成功')
    emit('graded')
    handleClose()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '评分失败')
  } finally {
    loading.value = false
  }
}
</script>
