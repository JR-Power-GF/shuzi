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
        path: 'teacher/dashboard',
        name: 'TeacherDashboard',
        component: () => import('../views/teacher/Dashboard.vue'),
        meta: { roles: ['teacher'] },
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
        path: 'admin/dashboard',
        name: 'AdminDashboard',
        component: () => import('../views/admin/Dashboard.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'admin/stats/courses',
        name: 'AdminCourseStats',
        component: () => import('../views/admin/CourseStats.vue'),
        meta: { roles: ['admin'] },
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
      {
        path: 'teacher/courses',
        name: 'TeacherCourseList',
        component: () => import('../views/teacher/CourseList.vue'),
        meta: { roles: ['teacher'] },
      },
      {
        path: 'teacher/courses/create',
        name: 'TeacherCourseCreate',
        component: () => import('../views/teacher/CourseCreate.vue'),
        meta: { roles: ['teacher'] },
      },
      {
        path: 'teacher/courses/:id',
        name: 'TeacherCourseDetail',
        component: () => import('../views/teacher/CourseDetail.vue'),
        meta: { roles: ['teacher'] },
      },
      {
        path: 'admin/courses',
        name: 'AdminCourseList',
        component: () => import('../views/admin/CourseList.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'student/courses',
        name: 'StudentCourseList',
        component: () => import('../views/student/CourseList.vue'),
        meta: { roles: ['student'] },
      },
      {
        path: 'student/courses/:id/summary',
        name: 'StudentCourseSummary',
        component: () => import('../views/student/CourseSummary.vue'),
        meta: { roles: ['student'] },
      },
      {
        path: 'admin/ai/config',
        name: 'AdminAIConfig',
        component: () => import('../views/admin/AIConfig.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'admin/ai/usage',
        name: 'AdminAIUsage',
        component: () => import('../views/admin/AIUsage.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'admin/ai/feedback',
        name: 'AdminAIFeedback',
        component: () => import('../views/admin/AIFeedback.vue'),
        meta: { roles: ['admin'] },
      },
      {
        path: 'admin/ai/prompts',
        name: 'AdminPromptTemplates',
        component: () => import('../views/admin/PromptTemplates.vue'),
        meta: { roles: ['admin'] },
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
