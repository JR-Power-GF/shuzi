<template>
  <div class="login-page">
    <!-- 左侧品牌区 -->
    <div class="login-brand">
      <div class="brand-decor brand-circle-1"></div>
      <div class="brand-decor brand-circle-2"></div>
      <div class="brand-decor brand-circle-3"></div>
      <div class="brand-content">
        <div class="brand-icon">
          <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="4" y="8" width="40" height="28" rx="3" stroke="rgba(255,255,255,0.9)" stroke-width="2.5"/>
            <path d="M16 20h16M16 26h10" stroke="rgba(255,255,255,0.6)" stroke-width="2" stroke-linecap="round"/>
            <path d="M24 36v6M18 42h12" stroke="rgba(255,255,255,0.9)" stroke-width="2.5" stroke-linecap="round"/>
          </svg>
        </div>
        <h1 class="brand-title">数字实训教学管理平台</h1>
        <p class="brand-subtitle">高效管理 · 精准教学 · 智慧实训</p>
        <div class="brand-features">
          <div class="feature-item">
            <span class="feature-dot"></span>
            <span>课程任务一站式管理</span>
          </div>
          <div class="feature-item">
            <span class="feature-dot"></span>
            <span>作业提交与智能批改</span>
          </div>
          <div class="feature-item">
            <span class="feature-dot"></span>
            <span>多维度成绩分析统计</span>
          </div>
        </div>
      </div>
      <div class="brand-wave">
        <svg viewBox="0 0 400 80" preserveAspectRatio="none">
          <path d="M0,60 C100,20 200,80 400,40 L400,80 L0,80 Z" fill="rgba(255,255,255,0.04)"/>
          <path d="M0,70 C150,30 250,80 400,50 L400,80 L0,80 Z" fill="rgba(255,255,255,0.03)"/>
        </svg>
      </div>
    </div>

    <!-- 右侧登录区 -->
    <div class="login-form-side">
      <div class="login-form-wrapper">
        <div class="form-header">
          <h2>欢迎登录</h2>
          <p>请输入您的账号信息</p>
        </div>
        <el-form :model="form" :rules="rules" ref="formRef" @submit.prevent="handleLogin" class="login-form">
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              size="large"
              :prefix-icon="UserIcon"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              :prefix-icon="LockIcon"
              show-password
            />
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              native-type="submit"
              :loading="loading"
              size="large"
              class="login-btn"
            >
              登 录
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, markRaw } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User as UserIcon, Lock as LockIcon } from '@element-plus/icons-vue'
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
.login-page {
  display: flex;
  min-height: 100vh;
  overflow: hidden;
}

/* 左侧品牌区 */
.login-brand {
  position: relative;
  flex: 0 0 48%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 40%, #1e3a5f 100%);
  overflow: hidden;
}

.brand-decor {
  position: absolute;
  border-radius: 50%;
  opacity: 0.08;
  background: #fff;
}

.brand-circle-1 {
  width: 400px;
  height: 400px;
  top: -120px;
  left: -100px;
}

.brand-circle-2 {
  width: 200px;
  height: 200px;
  bottom: 60px;
  right: -40px;
  opacity: 0.05;
}

.brand-circle-3 {
  width: 120px;
  height: 120px;
  bottom: 200px;
  left: 40px;
  opacity: 0.04;
}

.brand-wave {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  line-height: 0;
}

.brand-wave svg {
  width: 100%;
  height: 80px;
}

.brand-content {
  position: relative;
  z-index: 1;
  padding: 40px;
  max-width: 440px;
}

.brand-icon {
  width: 56px;
  height: 56px;
  margin-bottom: 28px;
}

.brand-icon svg {
  width: 100%;
  height: 100%;
}

.brand-title {
  color: #fff;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 2px;
  margin: 0 0 12px;
  line-height: 1.3;
}

.brand-subtitle {
  color: rgba(255, 255, 255, 0.6);
  font-size: 15px;
  letter-spacing: 3px;
  margin: 0 0 48px;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 12px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
}

.feature-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3b82f6;
  flex-shrink: 0;
}

/* 右侧登录区 */
.login-form-side {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
}

.login-form-wrapper {
  width: 380px;
  padding: 20px;
}

.form-header {
  margin-bottom: 36px;
}

.form-header h2 {
  font-size: 26px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 8px;
}

.form-header p {
  font-size: 14px;
  color: #94a3b8;
  margin: 0;
}

.login-form :deep(.el-input__wrapper) {
  border-radius: 8px;
  padding: 4px 12px;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 22px;
}

.login-btn {
  width: 100%;
  height: 44px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 4px;
  background: linear-gradient(135deg, #1e3a5f, #2563eb);
  border: none;
  transition: opacity 0.2s, transform 0.1s;
}

.login-btn:hover {
  opacity: 0.92;
}

.login-btn:active {
  transform: scale(0.99);
}

/* 响应式：移动端 */
@media (max-width: 768px) {
  .login-page {
    flex-direction: column;
  }

  .login-brand {
    flex: 0 0 auto;
    min-height: 200px;
    padding: 32px 24px 28px;
  }

  .brand-content {
    padding: 0;
    text-align: center;
  }

  .brand-icon {
    margin: 0 auto 16px;
  }

  .brand-title {
    font-size: 22px;
  }

  .brand-subtitle {
    margin-bottom: 16px;
  }

  .brand-features {
    display: none;
  }

  .login-form-side {
    flex: 1;
    padding: 20px;
  }

  .login-form-wrapper {
    width: 100%;
    max-width: 380px;
    padding: 0;
  }
}
</style>
