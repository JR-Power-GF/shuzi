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
      case 'admin': return '/admin/dashboard'
      case 'teacher': return '/teacher/dashboard'
      case 'student': return '/student/courses'
      default: return '/login'
    }
  }

  return { user, accessToken, isLoggedIn, userRole, mustChangePassword, login, logout, getHomeRoute }
})
