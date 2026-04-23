<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">班级管理</h3>
      <el-button type="primary" @click="showCreateDialog">新建班级</el-button>
    </div>
    <div style="margin-bottom: 16px">
      <el-select v-model="semesterFilter" placeholder="筛选学期" clearable style="width: 180px" @change="fetchClasses">
        <el-option label="2025-2026-2" value="2025-2026-2" />
        <el-option label="2025-2026-1" value="2025-2026-1" />
      </el-select>
    </div>
    <el-table :data="classes" v-loading="loading" stripe>
      <el-table-column prop="name" label="班级名称" min-width="150" />
      <el-table-column prop="semester" label="学期" width="130" />
      <el-table-column prop="teacher_name" label="教师" width="100" />
      <el-table-column prop="student_count" label="学生数" width="80" />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/admin/classes/${row.id}/roster`)">花名册</el-button>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑班级' : '新建班级'" width="450px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="班级名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="学期" prop="semester">
          <el-input v-model="form.semester" placeholder="如 2025-2026-2" />
        </el-form-item>
        <el-form-item label="教师">
          <el-input v-model="form.teacher_id" placeholder="教师ID（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'

const classes = ref([])
const loading = ref(false)
const semesterFilter = ref('')
const dialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const formRef = ref(null)

const form = reactive({ name: '', semester: '2025-2026-2', teacher_id: '' })
const rules = {
  name: [{ required: true, message: '请输入班级名称', trigger: 'blur' }],
  semester: [{ required: true, message: '请输入学期', trigger: 'blur' }],
}

async function fetchClasses() {
  loading.value = true
  try {
    const params = {}
    if (semesterFilter.value) params.semester = semesterFilter.value
    const resp = await api.get('/classes', { params })
    classes.value = resp.data.items
  } catch { ElMessage.error('获取班级列表失败') }
  finally { loading.value = false }
}

function showCreateDialog() {
  isEdit.value = false
  Object.assign(form, { name: '', semester: '2025-2026-2', teacher_id: '' })
  dialogVisible.value = true
}
function openEdit(cls) {
  isEdit.value = true
  Object.assign(form, { name: cls.name, semester: cls.semester, teacher_id: cls.teacher_id || '', _id: cls.id })
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const payload = { name: form.name, semester: form.semester }
    if (form.teacher_id) payload.teacher_id = parseInt(form.teacher_id)
    if (isEdit.value) {
      await api.put(`/classes/${form._id}`, payload)
      ElMessage.success('更新成功')
    } else {
      await api.post('/classes', payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchClasses()
  } catch (err) { ElMessage.error(err.response?.data?.detail || '操作失败') }
  finally { saving.value = false }
}

async function handleDelete(cls) {
  try {
    await ElMessageBox.confirm(`确认删除班级 "${cls.name}"？`, '删除班级')
    await api.delete(`/classes/${cls.id}`)
    ElMessage.success('删除成功')
    await fetchClasses()
  } catch (err) { if (err !== 'cancel') ElMessage.error(err.response?.data?.detail || '删除失败') }
}

onMounted(fetchClasses)
</script>
