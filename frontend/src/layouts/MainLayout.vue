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
          <el-menu-item index="/teacher/dashboard">
            <span>教学概览</span>
          </el-menu-item>
          <el-menu-item index="/teacher/courses">
            <span>课程管理</span>
          </el-menu-item>
          <el-menu-item index="/teacher/tasks">
            <span>我的任务</span>
          </el-menu-item>
          <el-menu-item index="/teacher/tasks/create">
            <span>创建任务</span>
          </el-menu-item>
        </template>
        <template v-if="auth.userRole === 'student'">
          <el-menu-item index="/student/courses">
            <span>我的课程</span>
          </el-menu-item>
          <el-menu-item index="/student/tasks">
            <span>我的任务</span>
          </el-menu-item>
        </template>
        <template v-if="auth.userRole === 'admin'">
          <el-menu-item index="/admin/dashboard">
            <span>系统概览</span>
          </el-menu-item>
          <el-menu-item index="/admin/stats/courses">
            <span>课程统计</span>
          </el-menu-item>
          <el-menu-item index="/admin/users">
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/classes">
            <span>班级管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/courses">
            <span>课程管理</span>
          </el-menu-item>
          <el-menu-item index="/admin/ai/config">
            <span>AI 配置</span>
          </el-menu-item>
          <el-menu-item index="/admin/ai/usage">
            <span>AI 使用记录</span>
          </el-menu-item>
          <el-menu-item index="/admin/ai/feedback">
            <span>AI 反馈</span>
          </el-menu-item>
          <el-menu-item index="/admin/ai/prompts">
            <span>Prompt 模板</span>
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
