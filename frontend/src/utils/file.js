// 文件下载 / 复制工具
export function downloadText(filename, content, mime = 'text/plain') {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

// 去掉 HTML 标签，取纯文本（用于复制/导出 AI 回答）
export function stripHtml(html) {
  const div = document.createElement('div')
  div.innerHTML = html
  return (div.textContent || div.innerText || '').trim()
}

// 复制到剪贴板，带降级方案（非 HTTPS / 旧浏览器）
export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch (_) {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    let ok = false
    try { ok = document.execCommand('copy') } catch (_) { /* noop */ }
    ta.remove()
    return ok
  }
}
