<template>
  <div>
    <el-upload
      ref="uploadRef"
      :action="uploadAction"
      :headers="uploadHeaders"
      :before-upload="beforeUpload"
      :on-success="handleSuccess"
      :on-error="handleError"
      :file-list="fileList"
      :on-remove="handleRemove"
      :limit="5"
      :on-exceed="handleExceed"
      drag
      multiple
    >
      <el-icon style="font-size: 40px; color: #c0c4cc"><UploadFilled /></el-icon>
      <div>将文件拖到此处，或点击上传</div>
      <template #tip>
        <div class="el-upload__tip">
          允许类型: {{ allowedTypes.join(', ') }}，单文件最大 {{ maxSizeMB }}MB
        </div>
      </template>
    </el-upload>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'

const props = defineProps({
  allowedTypes: { type: Array, default: () => ['.pdf', '.doc', '.docx'] },
  maxSizeMB: { type: Number, default: 50 },
})

const emit = defineEmits(['update:tokens'])

const uploadRef = ref(null)
const fileList = ref([])
const uploadedTokens = ref([])

const uploadAction = computed(() => `${import.meta.env.VITE_API_BASE_URL || '/api'}/files/upload`)
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('access_token')}`,
}))

function beforeUpload(file) {
  const ext = '.' + file.name.split('.').pop().toLowerCase()
  if (!props.allowedTypes.includes(ext)) {
    ElMessage.error(`不支持的文件类型: ${ext}`)
    return false
  }
  if (file.size > props.maxSizeMB * 1024 * 1024) {
    ElMessage.error(`文件大小超过 ${props.maxSizeMB}MB`)
    return false
  }
  return true
}

function handleSuccess(response) {
  uploadedTokens.value.push(response.file_token)
  emit('update:tokens', [...uploadedTokens.value])
}

function handleError() {
  ElMessage.error('文件上传失败')
}

function handleRemove(file) {
  const token = file.response?.file_token
  if (token) {
    uploadedTokens.value = uploadedTokens.value.filter((t) => t !== token)
    emit('update:tokens', [...uploadedTokens.value])
  }
}

function handleExceed() {
  ElMessage.warning('最多上传5个文件')
}

function clearFiles() {
  fileList.value = []
  uploadedTokens.value = []
  emit('update:tokens', [])
}

defineExpose({ clearFiles })
</script>
