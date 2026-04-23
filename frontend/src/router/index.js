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
      {
        path: 'admin/users',
        name: 'AdminUserList',
        component: () => import('../views/admin/UserList.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'admin/classes',
        name: 'AdminClassList',
        component: () => import('../views/admin/ClassList.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'admin/classes/:id/roster',
        name: 'AdminClassRoster',
        component: () => import('../views/admin/ClassRoster.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'teacher/tasks/:id/edit',
        name: 'TeacherTaskEdit',
        component: () => import('../views/teacher/TaskEdit.vue'),
        meta: { roles: ['teacher'] },
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
