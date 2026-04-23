<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">用户管理</h3>
      <el-button type="primary" @click="showCreateDialog">新建用户</el-button>
    </div>
    <div style="margin-bottom: 16px; display: flex; gap: 12px">
      <el-select v-model="roleFilter" placeholder="筛选角色" clearable style="width: 120px" @change="fetchUsers">
        <el-option label="管理员" value="admin" />
        <el-option label="教师" value="teacher" />
        <el-option label="学生" value="student" />
      </el-select>
      <el-input v-model="searchText" placeholder="搜索用户名或姓名" clearable style="width: 200px" @clear="fetchUsers" @keyup.enter="fetchUsers" />
    </div>
    <el-table :data="users" v-loading="loading" stripe>
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="real_name" label="姓名" width="100" />
      <el-table-column prop="role" label="角色" width="80">
        <template #default="{ row }">{{ roleLabel(row.role) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '正常' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="email" label="邮箱" min-width="150" />
      <el-table-column prop="phone" label="电话" width="120" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="warning" @click="handleResetPassword(row)">重置密码</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      style="margin-top: 16px; justify-content: center"
      :current-page="currentPage"
      :page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next"
      @current-change="handlePageChange"
    />

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新建用户'" width="500px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :disabled="isEdit" />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="form.real_name" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" :disabled="isEdit">
            <el-option label="管理员" value="admin" />
            <el-option label="教师" value="teacher" />
            <el-option label="学生" value="student" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
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

const users = ref([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const roleFilter = ref('')
const searchText = ref('')
const dialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const formRef = ref(null)

const form = reactive({ username: '', password: '', real_name: '', role: 'student', email: '', phone: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur', min: 8 }],
  real_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

function roleLabel(role) {
  const map = { admin: '管理员', teacher: '教师', student: '学生' }
  return map[role] || role
}

async function fetchUsers() {
  loading.value = true
  try {
    const params = { skip: (currentPage.value - 1) * pageSize, limit: pageSize }
    if (roleFilter.value) params.role = roleFilter.value
    if (searchText.value) params.search = searchText.value
    const resp = await api.get('/users', { params })
    users.value = resp.data.items
    total.value = resp.data.total
  } catch { ElMessage.error('获取用户列表失败') }
  finally { loading.value = false }
}

function handlePageChange(page) { currentPage.value = page; fetchUsers() }
function showCreateDialog() {
  isEdit.value = false
  Object.assign(form, { username: '', password: '', real_name: '', role: 'student', email: '', phone: '' })
  dialogVisible.value = true
}
function openEdit(user) {
  isEdit.value = true
  Object.assign(form, { username: user.username, real_name: user.real_name, role: user.role, email: user.email || '', phone: user.phone || '' })
  form._id = user.id
  dialogVisible.value = true
}

async function handleSave() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    if (isEdit.value) {
      await api.put(`/users/${form._id}`, { real_name: form.real_name, email: form.email, phone: form.phone })
      ElMessage.success('更新成功')
    } else {
      await api.post('/users', form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchUsers()
  } catch (err) { ElMessage.error(err.response?.data?.detail || '操作失败') }
  finally { saving.value = false }
}

async function handleResetPassword(user) {
  try {
    await ElMessageBox.confirm(`确认重置用户 "${user.real_name}" 的密码？`, '重置密码')
    await api.post(`/auth/reset-password/${user.id}`, { new_password: '12345678' })
    ElMessage.success('密码已重置为 12345678')
  } catch (err) { if (err !== 'cancel') ElMessage.error('重置失败') }
}

onMounted(fetchUsers)
</script>
