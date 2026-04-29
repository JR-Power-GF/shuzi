<template>
  <div>
    <h3 style="margin-bottom: 16px">Prompt 模板管理</h3>
    <el-table :data="templates" v-loading="loading" stripe>
      <el-table-column prop="name" label="模板名称" width="180" />
      <el-table-column prop="description" label="描述" min-width="150" />
      <el-table-column prop="variables" label="变量" width="200">
        <template #default="{ row }">{{ row.variables?.join(', ') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="editVisible" :title="'编辑: ' + editingName" width="600px">
      <el-input v-model="editText" type="textarea" :rows="10" />
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const templates = ref([])
const loading = ref(false)
const editVisible = ref(false)
const editingName = ref('')
const editText = ref('')
const saving = ref(false)

async function fetchTemplates() {
  loading.value = true
  try {
    const resp = await api.get('/prompts')
    templates.value = resp.data
  } catch { ElMessage.error('获取模板列表失败') }
  finally { loading.value = false }
}

function openEdit(template) {
  editingName.value = template.name
  editText.value = template.template_text
  editVisible.value = true
}

async function handleSave() {
  saving.value = true
  try {
    await api.put(`/prompts/${editingName.value}`, { template_text: editText.value })
    ElMessage.success('模板已更新')
    editVisible.value = false
    await fetchTemplates()
  } catch (err) { ElMessage.error(err.response?.data?.detail || '更新失败') }
  finally { saving.value = false }
}

onMounted(fetchTemplates)
</script>
