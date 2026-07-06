/**
 * 统一 API 客户端。
 *
 * 部署形态：BizBuddy 前端挂在 www.wuyullm.com/bizbuddy/ 子路径下，
 *          通过 nginx 反代到内部 :8010（前端静态资源）和 :8200（后端 API）。
 *
 * Auth 策略（无需前端管理 token）：
 *   - buildingai 登录后把 JWT 写进 `__user_token__` cookie（domain=www.wuyullm.com, path=/）
 *   - BizBuddy 与 buildingai 同源同域，浏览器请求 /bizbuddy/api/... 时自动带上该 cookie
 *   - BizBuddy 后端从 cookie 里读 token 校验（HS256 + 同 SECRET_KEY + payload.id）
 *   - 前端不再读写 localStorage token —— 登出交给 buildingai
 */

// 生产 Vite base 是 /bizbuddy/，同一份代码要能在 dev（base=/）与 prod 下都拼对 API 路径。
// import.meta.env.BASE_URL 由 Vite 注入，形如 "/bizbuddy/" 或 "/"。
const BASE = (import.meta.env.BASE_URL || '/').replace(/\/+$/, '') // 去尾 /
const API_PREFIX = `${BASE}/api/v1`

// 未登录 / 401 时跳到 buildingai 登录页。登录成功后 buildingai 会用 Nuxt navigateTo
// 跳回 redirect 参数指定的路径（同域内部路径，如 /bizbuddy/）。
const LOGIN_URL = 'https://www.wuyullm.com/login/'

/**
 * 未登录时跳登录页，参数用 buildingai 支持的 `redirect`。
 */
export function redirectToLogin() {
  // 回跳目标：当前 pathname + search + hash（相对 www.wuyullm.com 根，属于同域内部路径）。
  const back = window.location.pathname + window.location.search + window.location.hash
  const url = `${LOGIN_URL}?redirect=${encodeURIComponent(back)}`
  window.location.replace(url)
}

/**
 * 带鉴权的 fetch 封装。
 *
 * @param {string} path - 支持相对（"/agents"）自动拼上 /bizbuddy/api/v1；
 *                       也支持完整 API 路径（"/bizbuddy/api/v1/xxx"）或跨域绝对 URL。
 * @param {RequestInit} options
 * @returns {Promise<Response>}
 */
export async function apiFetch(path, options = {}) {
  let url
  if (path.startsWith('http')) {
    url = path
  } else if (path.startsWith(BASE + '/api/') || path.startsWith('/api/')) {
    // 前端调用方偶尔会显式写完整路径，两种前缀都兼容。
    url = path.startsWith(BASE) ? path : BASE + path
  } else {
    url = `${API_PREFIX}${path.startsWith('/') ? path : '/' + path}`
  }

  const headers = new Headers(options.headers || {})
  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json')
  }

  // 默认 credentials 是 same-origin，同域请求自然会带 __user_token__ cookie，
  // 但保留 include 更明确，也兼容将来跨域场景。
  const resp = await fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers,
  })

  if (resp.status === 401) {
    redirectToLogin()
    throw new Error('unauthorized')
  }

  return resp
}

/** JSON 快捷方法：非 2xx 抛错，204 返回 null。 */
export async function apiJson(path, options = {}) {
  const resp = await apiFetch(path, options)
  if (!resp.ok) {
    const text = await resp.text().catch(() => '')
    throw new Error(`HTTP ${resp.status}: ${text}`)
  }
  if (resp.status === 204) return null
  return resp.json()
}
