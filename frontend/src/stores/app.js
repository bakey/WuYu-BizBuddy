import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const activeTab = ref('chat')
  const backendStatus = ref('checking')   // 'checking' | 'online' | 'offline'

  function setTab(tab) {
    activeTab.value = tab
  }

  // GET /api/v1/health 探活：忠实契约 {status, version}，并对「挂起但在监听」的后端加超时兜底
  let inFlight = false
  async function checkHealth() {
    if (inFlight) return            // 防止 30s tick 与上一次未完成请求叠加并发
    inFlight = true
    try {
      // health 免鉴权，但 URL 需要带上 Vite base（部署在 /bizbuddy/ 子路径下）。
      const base = (import.meta.env.BASE_URL || '/').replace(/\/+$/, '')
      const resp = await fetch(`${base}/api/v1/health`, {
        cache: 'no-store',
        signal: AbortSignal.timeout(5000),   // 后端半开/挂起时落定为 offline，而非永久卡在 checking
      })
      const data = await resp.json().catch(() => null)
      backendStatus.value = (resp.ok && data?.status === 'ok') ? 'online' : 'offline'
    } catch (_) {
      backendStatus.value = 'offline'   // 连接拒绝 / 超时 / 非 JSON 均视为离线
    } finally {
      inFlight = false
    }
  }

  checkHealth()
  const healthTimer = setInterval(checkHealth, 30000)   // 周期探活：掉线/恢复都能反映
  // Vite HMR 热替换本模块时清掉旧定时器，避免开发期多个探活定时器叠加
  if (import.meta.hot) {
    import.meta.hot.dispose(() => clearInterval(healthTimer))
  }

  return { activeTab, setTab, backendStatus, checkHealth }
})
