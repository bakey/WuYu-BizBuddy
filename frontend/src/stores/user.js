import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { apiJson, redirectToLogin } from '@/utils/api'

/**
 * 当前登录用户。
 *
 * Auth 模型：session 完全靠 `__user_token__` cookie（buildingai 签发，跨 /bizbuddy 子路径共享）。
 * 前端只做：
 *   1. boot() 时调 /auth/me 探活；成功则 ready，失败或 401 跳登录页
 *   2. logout() 时调后端 logout（清 cookie）后跳登录页
 */
export const useUserStore = defineStore('user', () => {
  const user = ref(null)
  const loading = ref(false)
  const ready = ref(false)

  const isLoggedIn = computed(() => !!user.value)
  const displayName = computed(() => user.value?.nickname || user.value?.username || '')

  async function fetchMe() {
    user.value = await apiJson('/auth/me')
    return user.value
  }

  /** 页面启动时探活。成功 true；未登录已发起跳转，返回 false。 */
  async function boot() {
    loading.value = true
    try {
      try {
        await fetchMe()
        ready.value = true
        return true
      } catch (err) {
        // /auth/me 401 会在 apiFetch 里自动跳登录；这里兜底再跳一次。
        console.warn('boot /auth/me failed', err)
        redirectToLogin()
        return false
      }
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try {
      await apiJson('/auth/logout', { method: 'POST' })
    } catch (_) {
      // 登出接口失败也无所谓——反正马上跳去登录页
    }
    user.value = null
    redirectToLogin()
  }

  return { user, loading, ready, isLoggedIn, displayName, boot, fetchMe, logout }
})
