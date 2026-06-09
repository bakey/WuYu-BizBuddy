import { defineStore } from 'pinia'
import { ref, computed, markRaw } from 'vue'

// 模块级自增计数器：保证同一毫秒内并发上传也拿到唯一临时 id
let _tempSeq = 0

export const useKnowledgeStore = defineStore('knowledge', () => {
  const datasets = ref([
    { id: 1, icon: '📊', iconBg: 'var(--info-light)',    iconColor: 'var(--info)',    name: '企业内部固废处理工艺参数库',        count: '8,240 条', size: '1.2 GB', date: '2 天前', status: 'ok',   statusLabel: '已就绪',      linkedDb: 'policy_db',         linkedTag: 'tag-blue', progress: null },
    { id: 2, icon: '📑', iconBg: 'var(--primary-light)', iconColor: 'var(--primary)', name: '历史项目报告与合同文档',            count: '3,126 份', size: '860 MB', date: '5 天前', status: 'ok',   statusLabel: '已就绪',      linkedDb: null,                linkedTag: null,       progress: null },
    { id: 3, icon: '🛰️', iconBg: 'var(--warn-light)',    iconColor: 'var(--warn)',    name: '遥感监测图像数据集（2024-2026）', count: '1,114 张', size: '380 MB', date: '上传中…', status: 'warn', statusLabel: '处理中 72%', linkedDb: 'remote_sensing_db', linkedTag: 'tag-gray', progress: 72   },
    { id: 4, icon: '📦', iconBg: 'var(--purple-light)',  iconColor: 'var(--purple)',  name: '焚烧厂运营日报（2025 Q1-Q2）',   count: '540 份',   size: '72 MB',  date: '1 周前', status: 'ok',   statusLabel: '已就绪',      linkedDb: 'process_db',        linkedTag: 'tag-red',  progress: null }
  ])

  // 数据集数量从 datasets 派生，永远与表格一致；其余为静态展示指标
  const kpis = computed(() => ({
    datasets: datasets.value.length,
    docs: '12,480',
    size: '2.4',
    availability: '98.2'
  }))

  const groups = ref([
    { name: '全部数据集', icon: '📁', count: 8, meta: null,        active: true  },
    { name: '工艺参数',   icon: '📊', count: 2, meta: '链接 process_db', active: false },
    { name: '合同文档',   icon: '📑', count: 3, meta: null,        active: false },
    { name: '遥感图像',   icon: '🛰️', count: 1, meta: '上传中',    active: false },
    { name: '运营报表',   icon: '📦', count: 2, meta: null,        active: false }
  ])

  const indexStatuses = ref([
    { label: '已就绪', count: 6, checked: true  },
    { label: '处理中', count: 2, checked: true  },
    { label: '解析失败', count: 0, checked: false }
  ])

  const visibility = ref('me')

  const EXT_ICON_MAP = {
    CSV:  { icon: '📊', bg: 'var(--info-light)',    color: 'var(--info)'    },
    XLSX: { icon: '📊', bg: 'var(--info-light)',    color: 'var(--info)'    },
    PDF:  { icon: '📑', bg: 'var(--primary-light)', color: 'var(--primary)' },
    DOCX: { icon: '📄', bg: 'var(--primary-light)', color: 'var(--primary)' },
    DOC:  { icon: '📄', bg: 'var(--primary-light)', color: 'var(--primary)' },
    JSON: { icon: '🔗', bg: 'var(--purple-light)',  color: 'var(--purple)'  },
    ZIP:  { icon: '📦', bg: 'var(--warn-light)',    color: 'var(--warn)'    },
    TXT:  { icon: '📝', bg: 'var(--surface2)',      color: 'var(--ink2)'    }
  }

  // 后端 content 字段只接收文本，二进制格式（PDF/Excel/ZIP…）需走专门解析管线，
  // 直接 readAsText 会得到乱码，这里前置拦截
  const TEXT_EXTS = new Set(['CSV', 'JSON', 'TXT', 'MD', 'LOG', 'TSV', 'XML', 'YAML', 'YML'])

  function _spliceLocal(id) {
    const idx = datasets.value.findIndex(d => d.id === id)
    if (idx > -1) datasets.value.splice(idx, 1)
  }

  function _markErr(id, label) {
    const e = datasets.value.find(d => d.id === id)
    if (e) {
      e.status = 'err'
      e.statusLabel = label
      e.progress = null
      e._uploading = false
      e._abort = null
    }
  }

  function _readAsText(file, signal) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = e => resolve(e.target.result)
      reader.onerror = () => reject(new Error('文件读取失败'))
      if (signal) {
        signal.addEventListener('abort', () => {
          try { reader.abort() } catch (_) { /* noop */ }
          reject(new DOMException('aborted', 'AbortError'))
        })
      }
      reader.readAsText(file, 'utf-8')
    })
  }

  // 启动时从后端加载文档列表，后端不可用时静默保留 mock 数据
  async function loadDatasets() {
    try {
      const resp = await fetch('/api/v1/documents?limit=100')
      if (!resp.ok) return
      const docs = await resp.json()
      if (!docs.length) return
      datasets.value = docs.map(doc => {
        const src = doc.source || '未知来源'
        const ext = (src.split('.').pop() || '').toUpperCase()
        const ic = EXT_ICON_MAP[ext] || { icon: '📁', bg: 'var(--surface2)', color: 'var(--ink2)' }
        return {
          id: doc.id,
          icon: ic.icon, iconBg: ic.bg, iconColor: ic.color,
          name: src,
          count: `${doc.content.length} 字`,
          size: `${(doc.content.length / 1024).toFixed(1)} KB`,
          date: '已同步',
          status: 'ok', statusLabel: '已就绪',
          linkedDb: null, linkedTag: null,
          progress: null
        }
      })
    } catch (_) {
      // 后端离线，保留 mock 数据
    }
  }

  async function addDataset(file) {
    const ext = (file.name.split('.').pop() || '').toUpperCase()
    const ic = EXT_ICON_MAP[ext] || { icon: '📁', bg: 'var(--surface2)', color: 'var(--ink2)' }
    const tempId = `tmp-${++_tempSeq}`
    const controller = new AbortController()
    const ds = {
      id: tempId,
      _uploading: true,
      _abort: markRaw(controller),  // 不让 Vue 代理 AbortController
      icon: ic.icon, iconBg: ic.bg, iconColor: ic.color,
      name: file.name,
      count: `${(file.size / 1024).toFixed(0)} KB`,
      size: `${(file.size / 1024 / 1024).toFixed(1)} MB`,
      date: '刚刚',
      status: 'warn', statusLabel: '读取中…',
      linkedDb: null, linkedTag: null,
      progress: 20
    }
    datasets.value.push(ds)

    // 二进制文件不支持直传
    if (!TEXT_EXTS.has(ext)) {
      _markErr(tempId, '暂不支持二进制文件直传（需文本内容）')
      return
    }

    try {
      const content = await _readAsText(file, controller.signal)

      const found = datasets.value.find(d => d.id === tempId)
      if (!found) return  // 已被取消移除

      if (!content || !content.trim().length) {
        _markErr(tempId, '文件为空或无法解析为文本')
        return
      }

      found.progress = 60
      found.statusLabel = '上传中…'

      const resp = await fetch('/api/v1/documents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content,
          source: file.name,
          metadata: { size: file.size, type: file.type || ext }
        }),
        signal: controller.signal
      })

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const doc = await resp.json()

      const entry = datasets.value.find(d => d.id === tempId)
      if (entry) {
        entry.id = doc.id
        entry._uploading = false
        entry._abort = null
        entry.progress = 100
        entry.status = 'ok'
        entry.statusLabel = '已就绪'
        entry.count = `${content.length} 字`
      } else {
        // 条目在上传期间被取消，但 POST 已落库 → 补偿删除孤儿文档
        fetch(`/api/v1/documents/${doc.id}`, { method: 'DELETE' }).catch(() => {})
      }
    } catch (err) {
      if (err && err.name === 'AbortError') return  // 用户取消，条目已移除
      _markErr(tempId, `失败：${err.message}`)
    }
  }

  // 返回 boolean：true=已移除，false=后端删除失败（保留该行，由调用方提示）
  async function removeDataset(id) {
    const entry = datasets.value.find(d => d.id === id)
    if (!entry) return true

    // 上传中的临时条目：中止在途请求并本地移除
    if (entry._uploading) {
      if (entry._abort) entry._abort.abort()
      _spliceLocal(id)
      return true
    }

    // 失败条目无后端记录，直接本地移除
    if (entry.status === 'err') {
      _spliceLocal(id)
      return true
    }

    // 已就绪条目：调后端 DELETE
    try {
      const resp = await fetch(`/api/v1/documents/${id}`, { method: 'DELETE' })
      if (resp.ok || resp.status === 404) {  // 404 视为已删除（幂等）
        _spliceLocal(id)
        return true
      }
      return false  // 5xx：保留行
    } catch (_) {
      return false  // 网络异常：保留行
    }
  }

  function setGroup(name) {
    groups.value.forEach(g => { g.active = g.name === name })
  }

  function setVisibility(v) {
    visibility.value = v
  }

  loadDatasets()

  return { kpis, datasets, groups, indexStatuses, visibility, addDataset, removeDataset, setGroup, setVisibility }
})
