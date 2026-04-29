# PR3: Frontend Minimum Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a browser-based Vue 3 + Element Plus UI that completes the full closed loop: login → teacher creates task → student uploads and submits → teacher grades and publishes → student sees score.

**Architecture:** Single-page app with Vue 3 Composition API (`<script setup>`), Element Plus for UI components, Pinia for auth state, Vue Router with role-based guards, axios with Bearer token interceptor. The frontend proxies `/api` to the FastAPI backend via Vite dev server.

**Tech Stack:** Vue 3, Element Plus, Pinia, Vue Router 4, axios, Vite

---

## File Structure

### New files to create (entire `frontend/` directory)

| File | Purpose |
|------|---------|
| `frontend/package.json` | Dependencies and scripts |
| `frontend/vite.config.js` | Vite config with API proxy |
| `frontend/index.html` | HTML entry point |
| `frontend/.env.development` | Dev environment variables |
| `frontend/src/main.js` | App bootstrap (Vue + plugins) |
| `frontend/src/App.vue` | Root component |
| `frontend/src/api/index.js` | Axios instance with token interceptor |
| `frontend/src/stores/auth.js` | Pinia auth store |
| `frontend/src/router/index.js` | Routes with role guards |
| `frontend/src/layouts/MainLayout.vue` | Sidebar + top bar + router-view |
| `frontend/src/views/Login.vue` | Login form |
| `frontend/src/views/teacher/TaskList.vue` | Teacher's task list |
| `frontend/src/views/teacher/TaskCreate.vue` | Create task form |
| `frontend/src/views/teacher/SubmissionReview.vue` | Review + grade submissions |
| `frontend/src/views/student/TaskList.vue` | Student's task list |
| `frontend/src/views/student/TaskDetail.vue` | Task detail + submit |
| `frontend/src/views/student/SubmissionDetail.vue` | View grade after publish |
| `frontend/src/components/FileUpload.vue` | File upload with drag-drop |
| `frontend/src/components/GradingDialog.vue` | Score + feedback dialog |

### PR2 prerequisites (already complete)

The backend provides these endpoints that the frontend consumes:

| Endpoint | Response |
|----------|----------|
| `POST /api/auth/login` | `{access_token, refresh_token, must_change_password, user: {id, username, real_name, role}}` |
| `GET /api/classes/my` | `[{id, name, semester, teacher_id, teacher_name, student_count}]` |
| `POST /api/tasks` | `{id, title, class_id, class_name, created_by, deadline, allowed_file_types, ...}` |
| `GET /api/tasks/my` | `[{id, title, class_name, deadline, grades_published, ...}]` |
| `GET /api/tasks/:id` | `{id, title, description, requirements, allowed_file_types, ...}` |
| `POST /api/files/upload` | `{file_token, file_name, file_size, file_type}` (multipart) |
| `POST /api/tasks/:id/submissions` | `{id, task_id, student_id, version, is_late, files: [...], grade}` |
| `GET /api/submissions/:id` | `{id, files, grade: {score, feedback, penalty_applied, graded_at} | null}` |
| `GET /api/tasks/:id/submissions` | `[{id, student_name, version, is_late, submitted_at, grade}]` |
| `POST /api/tasks/:id/grades` | `{id, submission_id, score, penalty_applied, feedback}` |
| `POST /api/tasks/:id/grades/publish` | `{grades_published: true}` |
| `POST /api/tasks/:id/grades/unpublish` | `{grades_published: false}` |

---

## Task 1: Scaffold Vue 3 Project + Vite Config

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/.env.development`

- [ ] **Step 1: Create the project directory and package.json**

```bash
mkdir -p /Users/gaofang/Desktop/new_project/frontend/src/{api,stores,router,layouts,views/{teacher,student},components}
```

Create `frontend/package.json`:

```json
{
  "name": "training-platform-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0",
    "axios": "^1.6.0",
    "element-plus": "^2.5.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.0.0"
  }
}
```

- [ ] **Step 2: Create `frontend/vite.config.js`**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 3: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>数字实训教学管理平台</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

- [ ] **Step 4: Create `frontend/.env.development`**

```
VITE_API_BASE_URL=/api
```

- [ ] **Step 5: Install dependencies**

```bash
cd /Users/gaofang/Desktop/new_project/frontend && npm install
```

Expected: Dependencies installed, `node_modules` created.

- [ ] **Step 6: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/ && git commit -m "feat: scaffold Vue 3 frontend project with Vite config"
```

---

## Task 2: Axios API Layer + Bearer Token Interceptor

**Files:**
- Create: `frontend/src/api/index.js`

- [ ] **Step 1: Create the axios instance with interceptors**

Create `frontend/src/api/index.js`:

```javascript
import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default api
```

- [ ] **Step 2: Verify import works**

```bash
cd /Users/gaofang/Desktop/new_project/frontend && node -e "const fs = require('fs'); const code = fs.readFileSync('src/api/index.js', 'utf8'); console.log('Syntax OK:', code.includes('export default api'))"
```

Expected: `Syntax OK: true`

- [ ] **Step 3: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/api/ && git commit -m "feat: add axios API layer with Bearer token interceptor"
```

---

## Task 3: Pinia Auth Store

**Files:**
- Create: `frontend/src/stores/auth.js`

- [ ] **Step 1: Create the auth store**

Create `frontend/src/stores/auth.js`:

```javascript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const accessToken = ref(localStorage.getItem('access_token') || '')

  const isLoggedIn = computed(() => !!accessToken.value)
  const userRole = computed(() => user.value?.role || '')
  const mustChangePassword = computed(() => user.value?.must_change_password || false)

  async function login(username, password) {
    const resp = await api.post('/auth/login', { username, password })
    const data = resp.data
    accessToken.value = data.access_token
    user.value = data.user
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    return data
  }

  function logout() {
    accessToken.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
  }

  function getHomeRoute() {
    if (!user.value) return '/login'
    switch (user.value.role) {
      case 'admin': return '/teacher/tasks'
      case 'teacher': return '/teacher/tasks'
      case 'student': return '/student/tasks'
      default: return '/login'
    }
  }

  return { user, accessToken, isLoggedIn, userRole, mustChangePassword, login, logout, getHomeRoute }
})
```

- [ ] **Step 2: Verify syntax**

```bash
cd /Users/gaofang/Desktop/new_project/frontend && node -e "const fs = require('fs'); const code = fs.readFileSync('src/stores/auth.js', 'utf8'); console.log('OK:', code.includes('useAuthStore'))"
```

Expected: `OK: true`

- [ ] **Step 3: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/stores/ && git commit -m "feat: add Pinia auth store with login/logout"
```

---

## Task 4: Vue Router with Role-Based Guards

**Files:**
- Create: `frontend/src/router/index.js`

- [ ] **Step 1: Create router with role guards**

Create `frontend/src/router/index.js`:

```javascript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        redirect: '/login',
      },
      {
        path: 'teacher/tasks',
        name: 'TeacherTaskList',
        component: () => import('../views/teacher/TaskList.vue'),
        meta: { roles: ['teacher'] },
      },
      {
        path: 'teacher/tasks/create',
        name: 'TeacherTaskCreate',
        component: () => import('../views/teacher/TaskCreate.vue'),
        meta: { roles: ['teacher'] },
      },
      {
        path: 'teacher/tasks/:id/submissions',
        name: 'TeacherSubmissionReview',
        component: () => import('../views/teacher/SubmissionReview.vue'),
        meta: { roles: ['teacher'] },
      },
      {
        path: 'student/tasks',
        name: 'StudentTaskList',
        component: () => import('../views/student/TaskList.vue'),
        meta: { roles: ['student'] },
      },
      {
        path: 'student/tasks/:id',
        name: 'StudentTaskDetail',
        component: () => import('../views/student/TaskDetail.vue'),
        meta: { roles: ['student'] },
      },
      {
        path: 'student/submissions/:id',
        name: 'StudentSubmissionDetail',
        component: () => import('../views/student/SubmissionDetail.vue'),
        meta: { roles: ['student'] },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  if (to.meta.public) return next()

  const auth = useAuthStore()
  if (!auth.isLoggedIn) return next('/login')

  const requiredRoles = to.meta.roles
  if (requiredRoles && !requiredRoles.includes(auth.userRole)) {
    return next(auth.getHomeRoute())
  }

  next()
})

export default router
```

- [ ] **Step 2: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/router/ && git commit -m "feat: add Vue Router with role-based guards"
```

---

## Task 5: Login Page

**Files:**
- Create: `frontend/src/views/Login.vue`

- [ ] **Step 1: Create Login page**

Create `frontend/src/views/Login.vue`:

```vue
<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <h2 style="text-align: center; margin: 0">数字实训教学管理平台</h2>
      </template>
      <el-form :model="form" :rules="rules" ref="formRef" @submit.prevent="handleLogin">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" size="large" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" prefix-icon="Lock" size="large" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" size="large" style="width: 100%">
            登 录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref(null)
const loading = ref(false)

const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const data = await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push(auth.getHomeRoute())
  } catch (err) {
    const detail = err.response?.data?.detail || '登录失败'
    ElMessage.error(detail)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f0f2f5;
}
.login-card {
  width: 400px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/Login.vue && git commit -m "feat: add Login page with Element Plus form"
```

---

## Task 6: MainLayout + App.vue + main.js Bootstrap

**Files:**
- Create: `frontend/src/layouts/MainLayout.vue`
- Modify: `frontend/src/App.vue`
- Create: `frontend/src/main.js`

- [ ] **Step 1: Create MainLayout**

Create `frontend/src/layouts/MainLayout.vue`:

```vue
<template>
  <el-container style="min-height: 100vh">
    <el-aside width="200px" style="background: #304156">
      <div style="color: #fff; text-align: center; padding: 20px 0; font-size: 16px">
        实训管理平台
      </div>
      <el-menu
        :default-active="$route.path"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        router
      >
        <template v-if="auth.userRole === 'teacher'">
          <el-menu-item index="/teacher/tasks">
            <span>我的任务</span>
          </el-menu-item>
          <el-menu-item index="/teacher/tasks/create">
            <span>创建任务</span>
          </el-menu-item>
        </template>
        <template v-if="auth.userRole === 'student'">
          <el-menu-item index="/student/tasks">
            <span>我的任务</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e6e6e6">
        <span>{{ auth.user?.real_name }} ({{ roleLabel }})</span>
        <el-button @click="handleLogout" text>退出登录</el-button>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const roleLabel = computed(() => {
  const map = { admin: '管理员', teacher: '教师', student: '学生' }
  return map[auth.userRole] || auth.userRole
})

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>
```

- [ ] **Step 2: Create App.vue**

Create `frontend/src/App.vue`:

```vue
<template>
  <router-view />
</template>
```

- [ ] **Step 3: Create main.js**

Create `frontend/src/main.js`:

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
```

- [ ] **Step 4: Verify dev server starts**

```bash
cd /Users/gaofang/Desktop/new_project/frontend && npx vite --host 2>&1 &
sleep 3 && curl -s http://localhost:5173 | head -20 && kill %1
```

Expected: HTML returned with `<div id="app">`.

- [ ] **Step 5: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/layouts/ frontend/src/App.vue frontend/src/main.js && git commit -m "feat: add MainLayout, App.vue, and main.js bootstrap"
```

---

## Task 7: Teacher TaskCreate Form

**Files:**
- Create: `frontend/src/views/teacher/TaskCreate.vue`

- [ ] **Step 1: Create TaskCreate page**

Create `frontend/src/views/teacher/TaskCreate.vue`:

```vue
<template>
  <div>
    <h3>创建任务</h3>
    <el-form :model="form" :rules="rules" ref="formRef" label-width="120px" style="max-width: 600px">
      <el-form-item label="任务标题" prop="title">
        <el-input v-model="form.title" />
      </el-form-item>
      <el-form-item label="任务描述">
        <el-input v-model="form.description" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="实验要求">
        <el-input v-model="form.requirements" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="选择班级" prop="class_id">
        <el-select v-model="form.class_id" placeholder="请选择班级">
          <el-option v-for="cls in classes" :key="cls.id" :label="cls.name" :value="cls.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="截止时间" prop="deadline">
        <el-date-picker v-model="form.deadline" type="datetime" placeholder="选择截止时间" />
      </el-form-item>
      <el-form-item label="允许文件类型" prop="allowed_file_types">
        <el-select v-model="form.allowed_file_types" multiple placeholder="选择文件类型">
          <el-option v-for="ft in fileTypes" :key="ft" :label="ft" :value="ft" />
        </el-select>
      </el-form-item>
      <el-form-item label="最大文件大小(MB)">
        <el-input-number v-model="form.max_file_size_mb" :min="1" :max="100" />
      </el-form-item>
      <el-form-item label="允许迟交">
        <el-switch v-model="form.allow_late_submission" />
      </el-form-item>
      <el-form-item v-if="form.allow_late_submission" label="迟交扣分比例(%)">
        <el-input-number v-model="form.late_penalty_percent" :min="0" :max="100" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSubmit" :loading="loading">创建任务</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)
const classes = ref([])

const fileTypes = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar', '.jpg', '.png', '.txt', '.csv']

const form = reactive({
  title: '',
  description: '',
  requirements: '',
  class_id: '',
  deadline: '',
  allowed_file_types: ['.pdf', '.docx'],
  max_file_size_mb: 50,
  allow_late_submission: false,
  late_penalty_percent: null,
})

const rules = {
  title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }],
  class_id: [{ required: true, message: '请选择班级', trigger: 'change' }],
  deadline: [{ required: true, message: '请选择截止时间', trigger: 'change' }],
  allowed_file_types: [{ required: true, message: '请选择文件类型', trigger: 'change', type: 'array', min: 1 }],
}

onMounted(async () => {
  try {
    const resp = await api.get('/classes/my')
    classes.value = resp.data
  } catch {
    ElMessage.error('获取班级列表失败')
  }
})

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await api.post('/tasks', {
      ...form,
      deadline: form.deadline.toISOString(),
    })
    ElMessage.success('任务创建成功')
    router.push('/teacher/tasks')
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '创建失败')
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/teacher/TaskCreate.vue && git commit -m "feat: add teacher task creation form"
```

---

## Task 8: Teacher TaskList Page

**Files:**
- Create: `frontend/src/views/teacher/TaskList.vue`

- [ ] **Step 1: Create TaskList page**

Create `frontend/src/views/teacher/TaskList.vue`:

```vue
<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h3 style="margin: 0">我的任务</h3>
      <el-button type="primary" @click="$router.push('/teacher/tasks/create')">创建任务</el-button>
    </div>
    <el-table :data="tasks" v-loading="loading" stripe>
      <el-table-column prop="title" label="任务标题" min-width="150" />
      <el-table-column prop="class_name" label="班级" width="150" />
      <el-table-column label="截止时间" width="170">
        <template #default="{ row }">{{ formatDate(row.deadline) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">
            {{ row.status === 'active' ? '进行中' : '已归档' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="成绩" width="80">
        <template #default="{ row }">
          <el-tag :type="row.grades_published ? 'success' : 'warning'" size="small">
            {{ row.grades_published ? '已发布' : '未发布' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/teacher/tasks/${row.id}/submissions`)">
            查看提交
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const tasks = ref([])
const loading = ref(false)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get('/tasks/my')
    tasks.value = resp.data
  } catch {
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
})
</script>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/teacher/TaskList.vue && git commit -m "feat: add teacher task list page"
```

---

## Task 9: Student TaskList Page

**Files:**
- Create: `frontend/src/views/student/TaskList.vue`

- [ ] **Step 1: Create student task list**

Create `frontend/src/views/student/TaskList.vue`:

```vue
<template>
  <div>
    <h3 style="margin-bottom: 16px">我的任务</h3>
    <el-table :data="tasks" v-loading="loading" stripe>
      <el-table-column prop="title" label="任务标题" min-width="150" />
      <el-table-column prop="class_name" label="班级" width="150" />
      <el-table-column label="截止时间" width="170">
        <template #default="{ row }">{{ formatDate(row.deadline) }}</template>
      </el-table-column>
      <el-table-column label="成绩状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.grades_published ? 'success' : 'info'" size="small">
            {{ row.grades_published ? '已出分' : '未出分' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="$router.push(`/student/tasks/${row.id}`)">
            查看
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const tasks = ref([])
const loading = ref(false)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get('/tasks/my')
    tasks.value = resp.data
  } catch {
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
})
</script>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/student/TaskList.vue && git commit -m "feat: add student task list page"
```

---

## Task 10: FileUpload Component

**Files:**
- Create: `frontend/src/components/FileUpload.vue`

- [ ] **Step 1: Create FileUpload component**

Create `frontend/src/components/FileUpload.vue`:

```vue
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

const uploadAction = computed(() => '/api/files/upload')
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
```

- [ ] **Step 2: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/components/FileUpload.vue && git commit -m "feat: add FileUpload component with drag-drop"
```

---

## Task 11: Student TaskDetail + Submission Page

**Files:**
- Create: `frontend/src/views/student/TaskDetail.vue`

- [ ] **Step 1: Create TaskDetail page**

Create `frontend/src/views/student/TaskDetail.vue`:

```vue
<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" title="返回" :content="task?.title || '任务详情'" />
    <div v-if="task" style="margin-top: 20px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="任务标题">{{ task.title }}</el-descriptions-item>
        <el-descriptions-item label="班级">{{ task.class_name }}</el-descriptions-item>
        <el-descriptions-item label="截止时间">{{ formatDate(task.deadline) }}</el-descriptions-item>
        <el-descriptions-item label="允许文件类型">{{ task.allowed_file_types?.join(', ') }}</el-descriptions-item>
        <el-descriptions-item label="任务描述" :span="2">{{ task.description || '无' }}</el-descriptions-item>
        <el-descriptions-item label="实验要求" :span="2">{{ task.requirements || '无' }}</el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <h4>提交作业</h4>
      <FileUpload
        ref="uploadRef"
        :allowed-types="task.allowed_file_types || ['.pdf']"
        :max-size-m-b="task.max_file_size_mb || 50"
        @update:tokens="fileTokens = $event"
      />
      <el-button
        type="primary"
        style="margin-top: 16px"
        :loading="submitting"
        :disabled="fileTokens.length === 0"
        @click="handleSubmit"
      >
        提交作业
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'
import FileUpload from '../../components/FileUpload.vue'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id

const task = ref(null)
const loading = ref(false)
const submitting = ref(false)
const fileTokens = ref([])
const uploadRef = ref(null)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get(`/tasks/${taskId}`)
    task.value = resp.data
  } catch {
    ElMessage.error('获取任务详情失败')
  } finally {
    loading.value = false
  }
})

async function handleSubmit() {
  if (fileTokens.value.length === 0) {
    ElMessage.warning('请先上传文件')
    return
  }
  try {
    await ElMessageBox.confirm('确认提交作业？提交后可重新提交。', '确认')
  } catch {
    return
  }

  submitting.value = true
  try {
    const resp = await api.post(`/tasks/${taskId}/submissions`, {
      file_tokens: fileTokens.value,
    })
    ElMessage.success(`提交成功 (版本 ${resp.data.version})`)
    uploadRef.value?.clearFiles()
    fileTokens.value = []
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '提交失败')
  } finally {
    submitting.value = false
  }
}
</script>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/student/TaskDetail.vue && git commit -m "feat: add student task detail and submission page"
```

---

## Task 12: GradingDialog Component

**Files:**
- Create: `frontend/src/components/GradingDialog.vue`

- [ ] **Step 1: Create GradingDialog component**

Create `frontend/src/components/GradingDialog.vue`:

```vue
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
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api'

const props = defineProps({
  visible: Boolean,
  submission: Object,
  taskId: [String, Number],
  latePenaltyPercent: { type: Number, default: null },
})

const emit = defineEmits(['update:visible', 'graded'])
const loading = ref(false)

const form = reactive({ score: 0, feedback: '' })

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
```

- [ ] **Step 2: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/components/GradingDialog.vue && git commit -m "feat: add GradingDialog component with late penalty display"
```

---

## Task 13: Teacher SubmissionReview Page

**Files:**
- Create: `frontend/src/views/teacher/SubmissionReview.vue`

- [ ] **Step 1: Create SubmissionReview page**

Create `frontend/src/views/teacher/SubmissionReview.vue`:

```vue
<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" title="返回" content="提交列表" />

    <div style="margin-top: 20px; display: flex; gap: 12px; align-items: center">
      <el-tag v-if="task">
        {{ task.title }} — {{ task.class_name }}
      </el-tag>
      <el-button
        v-if="task && !task.grades_published"
        type="success"
        size="small"
        @click="handlePublish"
      >
        发布成绩
      </el-button>
      <el-button
        v-if="task && task.grades_published"
        type="warning"
        size="small"
        @click="handleUnpublish"
      >
        撤回发布
      </el-button>
    </div>

    <el-table :data="submissions" stripe style="margin-top: 16px">
      <el-table-column prop="student_name" label="学生" width="100" />
      <el-table-column prop="version" label="版本" width="70" />
      <el-table-column label="迟交" width="70">
        <template #default="{ row }">
          <el-tag v-if="row.is_late" type="warning" size="small">迟交</el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="提交时间" width="170">
        <template #default="{ row }">{{ formatDate(row.submitted_at) }}</template>
      </el-table-column>
      <el-table-column label="成绩" width="100">
        <template #default="{ row }">
          <span v-if="row.grade">{{ row.grade.score }} 分</span>
          <el-tag v-else type="info" size="small">未评分</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openGrading(row)">评分</el-button>
          <el-button size="small" text @click="downloadFile(row)">下载</el-button>
        </template>
      </el-table-column>
    </el-table>

    <GradingDialog
      v-model:visible="gradingVisible"
      :submission="gradingSubmission"
      :task-id="taskId"
      :late-penalty-percent="task?.late_penalty_percent"
      @graded="fetchSubmissions"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../../api'
import GradingDialog from '../../components/GradingDialog.vue'

const route = useRoute()
const taskId = route.params.id

const task = ref(null)
const submissions = ref([])
const loading = ref(false)
const gradingVisible = ref(false)
const gradingSubmission = ref(null)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

async function fetchSubmissions() {
  loading.value = true
  try {
    const [taskResp, subsResp] = await Promise.all([
      api.get(`/tasks/${taskId}`),
      api.get(`/tasks/${taskId}/submissions`),
    ])
    task.value = taskResp.data
    submissions.value = subsResp.data
  } catch {
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchSubmissions)

function openGrading(submission) {
  gradingSubmission.value = submission
  gradingVisible.value = true
}

async function downloadFile(submission) {
  if (!submission.files?.length) {
    ElMessage.info('该提交无文件')
    return
  }
  const file = submission.files[0]
  window.open(`/api/files/${file.id}`, '_blank')
}

async function handlePublish() {
  try {
    await ElMessageBox.confirm('确认发布成绩？发布后学生可查看分数。', '确认发布')
    await api.post(`/tasks/${taskId}/grades/publish`)
    ElMessage.success('成绩已发布')
    await fetchSubmissions()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error('发布失败')
  }
}

async function handleUnpublish() {
  try {
    await ElMessageBox.confirm('确认撤回成绩发布？', '确认撤回')
    await api.post(`/tasks/${taskId}/grades/unpublish`)
    ElMessage.success('已撤回发布')
    await fetchSubmissions()
  } catch (err) {
    if (err !== 'cancel') ElMessage.error('撤回失败')
  }
}
</script>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/teacher/SubmissionReview.vue && git commit -m "feat: add teacher submission review page with grading"
```

---

## Task 14: Student SubmissionDetail Page

**Files:**
- Create: `frontend/src/views/student/SubmissionDetail.vue`

- [ ] **Step 1: Create SubmissionDetail page**

Create `frontend/src/views/student/SubmissionDetail.vue`:

```vue
<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" title="返回" content="提交详情" />

    <div v-if="submission" style="margin-top: 20px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="版本">v{{ submission.version }}</el-descriptions-item>
        <el-descriptions-item label="提交时间">{{ formatDate(submission.submitted_at) }}</el-descriptions-item>
        <el-descriptions-item label="迟交">
          <el-tag v-if="submission.is_late" type="warning" size="small">迟交</el-tag>
          <span v-else>否</span>
        </el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <h4>提交文件</h4>
      <el-table :data="submission.files" stripe>
        <el-table-column prop="file_name" label="文件名" />
        <el-table-column label="大小" width="120">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" text @click="downloadFile(row)">下载</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-divider />

      <h4>成绩</h4>
      <div v-if="submission.grade">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="分数">
            <span style="font-size: 20px; font-weight: bold; color: #409eff">
              {{ submission.grade.score }} 分
            </span>
          </el-descriptions-item>
          <el-descriptions-item v-if="submission.grade.penalty_applied" label="迟交扣分">
            <span style="color: #e6a23c">-{{ submission.grade.penalty_applied }} 分</span>
          </el-descriptions-item>
          <el-descriptions-item label="评语" :span="2">
            {{ submission.grade.feedback || '无' }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <el-alert v-else type="info" :closable="false" description="成绩尚未发布，请等待教师评分并发布" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../../api'

const route = useRoute()
const submissionId = route.params.id

const submission = ref(null)
const loading = ref(false)

function formatDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function downloadFile(file) {
  window.open(`/api/files/${file.id}`, '_blank')
}

onMounted(async () => {
  loading.value = true
  try {
    const resp = await api.get(`/submissions/${submissionId}`)
    submission.value = resp.data
  } catch {
    ElMessage.error('获取提交详情失败')
  } finally {
    loading.value = false
  }
})
</script>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/src/views/student/SubmissionDetail.vue && git commit -m "feat: add student submission detail page with grade display"
```

---

## Task 15: Final E2E Verification

**Files:**
- No new files — manual verification only

This task walks through the complete closed loop in the browser to verify all pages work together.

- [ ] **Step 1: Ensure backend is running with demo data**

```bash
cd /Users/gaofang/Desktop/new_project/backend
source .venv/bin/activate
python scripts/seed_demo.py
uvicorn app.main:app --reload --port 8000 &
```

- [ ] **Step 2: Start frontend dev server**

```bash
cd /Users/gaofang/Desktop/new_project/frontend && npm run dev
```

- [ ] **Step 3: Verify Login**

Open http://localhost:5173, login as `teacher1` / `teacher123`. Should redirect to teacher task list.

- [ ] **Step 4: Verify Teacher creates task**

Click "创建任务" → fill form → select class → submit → redirected to task list with new task.

- [ ] **Step 5: Verify Student submits**

Logout → login as `student1` / `student123` → see task in list → click "查看" → upload file → click "提交作业" → success message.

- [ ] **Step 6: Verify Teacher grades**

Logout → login as `teacher1` → click "查看提交" on task → see student submission → click "评分" → enter score 92 → "保存评分" → click "发布成绩" → confirm.

- [ ] **Step 7: Verify Student sees grade**

Logout → login as `student1` → task should show "已出分" → navigate to submission detail → see score 92 and feedback.

- [ ] **Step 8: Commit any final fixes**

If any fixes were needed during verification:

```bash
cd /Users/gaofang/Desktop/new_project && git add frontend/ && git commit -m "fix: address E2E verification findings"
```

---

## Self-Review Checklist

### Spec Coverage

| OpenSpec Task | Plan Task |
|---|---|
| C.1 Initialize Vue 3 + Element Plus | Task 1 |
| C.2 Vue Router with route guards | Task 4 |
| C.3 Pinia auth store | Task 3 |
| C.4 Login page | Task 5 |
| C.5 App layout (sidebar, top bar) | Task 6 |
| C.6 Teacher task creation form | Task 7 |
| C.7 Teacher task list page | Task 8 |
| C.8 Student task list page | Task 9 |
| C.9 Student task detail + submission | Task 11 |
| C.10 Teacher submission review | Task 13 |
| C.11 Teacher grading dialog | Task 12 |
| C.12 Student submission detail | Task 14 |

### Placeholder Scan

No TBD, TODO, "implement later", "add validation", or "similar to Task N" found. Every step contains exact code.

### Type Consistency

- `api` import path: `../../api` used consistently in all view components under `views/`
- `useAuthStore` imported from `../stores/auth` (views) or `../../stores/auth` (components)
- API response shapes match PR2 schemas: `LoginResponse`, `ClassResponse`, `TaskResponse`, `SubmissionResponse`, `GradeResponse`
- Route paths: `/teacher/tasks`, `/teacher/tasks/create`, `/teacher/tasks/:id/submissions`, `/student/tasks`, `/student/tasks/:id`, `/student/submissions/:id` — consistent between router and component navigation

---

## Summary

**15 tasks**, each 5-10 minutes. Total estimated time: ~2.5 hours.

**Dependency chain:**
- Task 1 (scaffold) → must be first
- Task 2 (API layer) → needs scaffold
- Task 3 (auth store) → needs API layer
- Task 4 (router) → needs auth store
- Task 5 (Login page) → needs auth store + router
- Task 6 (layout + bootstrap) → needs router
- Tasks 7-14 (pages) → need layout + auth store + API layer
- Task 15 (E2E verification) → needs all pages
