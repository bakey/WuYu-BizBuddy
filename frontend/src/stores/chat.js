import { defineStore } from 'pinia'
import { onMounted, ref, reactive } from 'vue'

const STREAM_RESPONSES = [
  '已检索 3 个数据库，找到 12 篇高相关政策文件。让我逐一对比关键条款...',
  '基于您的问题，我调用了 [政策检索] + [条文比对] 两项技能，结果如下：',
  '我注意到您关注的是危废处置政策。根据最新数据，2025 年 4 季度全国危废处置量同比增长 8.2%。',
  '已调用 [影响评估]，对此政策的潜在影响进行了综合评估，主要风险点包括以下几个方面...'
]

export const useChatStore = defineStore('chat', () => {
  const currentAgent = reactive({
    name: '政策解析专家',
    icon: '📄',
    bg: 'var(--primary-light)',
    color: 'var(--primary)',
    skillCount: 4
  })

  const dataSources = ref([
    { id: 1, name: '政策法规库', count: '12.4万', checked: true },
    { id: 2, name: '学术论文',   count: '86万',   checked: true },
    { id: 3, name: '企业数据',   count: '3.2万',  checked: false },
    { id: 4, name: '知识图谱',   count: '280万',  checked: false }
  ])

  const taskHistory = ref([])
  const loadingTasks = ref(false)

  const messages = ref([
    {
      id: 1, role: 'ai', sender: '政策解析专家', time: '14:30',
      content: '您好！我是<strong>政策解析专家</strong>，我自带 <strong>政策检索</strong>、<strong>条文比对</strong>、<strong>影响评估</strong>、<strong>合规清单</strong> 4 个技能。请描述您要研究的政策问题。'
    }
  ])

  const citations = ref([])

  let _nextId = messages.value.length + 1

  async function api(path, options = {}) {
    const resp = await fetch(`/api/v1${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options
    })
    if (!resp.ok) {
      const text = await resp.text()
      throw new Error(`HTTP ${resp.status}: ${text}`)
    }
    return resp.status === 204 ? null : resp.json()
  }

  function _mapTask(t) {
    return {
      id: t.id,
      title: t.title,
      meta: t.meta || `${currentAgent.name} · 刚刚`,
      pin: t.pin || '',
      pinned: t.pinned,
      active: t.active,
      agentName: t.agent_name,
      agentIcon: t.agent_icon
    }
  }

  async function loadTasks() {
    loadingTasks.value = true
    try {
      const items = await api('/chat/tasks')
      taskHistory.value = items.map(_mapTask)
    } catch (err) {
      console.error('加载任务历史失败', err)
    } finally {
      loadingTasks.value = false
    }
  }

  async function createTask(title = '新对话', options = {}) {
    const payload = {
      title,
      meta: options.meta || `${currentAgent.name} · 刚刚`,
      pinned: options.pinned || false,
      agent_name: currentAgent.name,
      agent_icon: currentAgent.icon
    }
    const t = await api('/chat/tasks', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
    const mapped = _mapTask(t)
    taskHistory.value.unshift(mapped)
    await activateTask(mapped.id)
    return mapped
  }

  async function activateTask(id) {
    const t = await api(`/chat/tasks/${id}/activate`, { method: 'POST' })
    const updated = _mapTask(t)
    taskHistory.value = taskHistory.value.map(item =>
      item.id === updated.id ? updated : { ...item, active: false }
    )
    return updated
  }

  async function togglePinTask(id) {
    const t = await api(`/chat/tasks/${id}/pin`, { method: 'POST' })
    const updated = _mapTask(t)
    const idx = taskHistory.value.findIndex(item => item.id === updated.id)
    if (idx > -1) {
      taskHistory.value[idx] = updated
    }
    await loadTasks()
    return updated
  }

  async function deleteTask(id) {
    await api(`/chat/tasks/${id}`, { method: 'DELETE' })
    taskHistory.value = taskHistory.value.filter(item => item.id !== id)
  }

  function setActiveTask(id) {
    const found = taskHistory.value.find(t => t.id === id)
    if (found && !found.active) {
      activateTask(id)
    }
  }

  function toggleDataSource(id) {
    const ds = dataSources.value.find(d => d.id === id)
    if (ds) ds.checked = !ds.checked
  }

  async function sendMessage(text) {
    const now = new Date().toTimeString().slice(0, 5)
    messages.value.push({ id: _nextId++, role: 'user', time: now, content: text })

    const thinkId = _nextId++
    messages.value.push({
      id: thinkId, role: 'ai', sender: currentAgent.name,
      time: now, thinking: '正在检索相关资料…'
    })

    try {
      const resp = await fetch('/api/v1/query/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, top_k: 5 })
      })

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let accText = ''
      let msgRefs = []
      let started = false
      let eventType = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop()

        for (const line of lines) {
          if (line === '') {
            eventType = ''
          } else if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const raw = line.slice(6)
            if (raw === '[DONE]') continue
            const data = JSON.parse(raw)

            if (eventType === 'references') {
              msgRefs = data.map((r, i) => ({
                num: i + 1,
                label: r.source || `引用 ${i + 1}`,
                source: r.source || `引用 ${i + 1}`,
                content: r.content || '',
                score: r.score
              }))
              citations.value = data.map((r, i) => ({
                id: i + 1,
                title: r.source || `文档片段 ${i + 1}`,
                meta: `[${i + 1}] 相似度 ${(r.score * 100).toFixed(0)}%`,
                relevance: r.score >= 0.85 ? 'high' : 'mid',
                source: r.source || `文档片段 ${i + 1}`,
                content: r.content || '',
                score: r.score
              }))
            } else if (eventType === 'delta') {
              accText += data.delta
              const idx = messages.value.findIndex(m => m.id === thinkId)
              if (idx > -1) {
                if (!started) {
                  started = true
                  messages.value[idx] = {
                    id: thinkId, role: 'ai', sender: currentAgent.name,
                    time: new Date().toTimeString().slice(0, 5),
                    content: accText, citations: [], actions: []
                  }
                } else {
                  messages.value[idx].content = accText
                }
              }
            } else if (eventType === 'error') {
              throw new Error(data.error)
            }
          }
        }
      }

      const idx = messages.value.findIndex(m => m.id === thinkId)
      if (idx > -1) {
        if (!started) {
          messages.value[idx] = {
            id: thinkId, role: 'ai', sender: currentAgent.name,
            time: new Date().toTimeString().slice(0, 5),
            content: accText || '（本次未生成回答）',
            citations: msgRefs, actions: []
          }
        } else {
          messages.value[idx].citations = msgRefs
          messages.value[idx].actions = [
            { label: '追问', variant: 'green' }, { label: '复制' }, { label: '导出' }
          ]
        }
      }
    } catch (err) {
      const idx = messages.value.findIndex(m => m.id === thinkId)
      if (idx > -1) {
        messages.value[idx] = {
          id: thinkId, role: 'ai', sender: currentAgent.name,
          time: new Date().toTimeString().slice(0, 5),
          content: `请求失败：${err.message}`,
          citations: [], actions: []
        }
      }
    }
  }

  function setCurrentAgent(agent) {
    Object.assign(currentAgent, agent)
  }

  onMounted(() => {
    loadTasks()
  })

  return {
    currentAgent, dataSources, taskHistory, messages, citations, loadingTasks,
    loadTasks, createTask, activateTask, togglePinTask, deleteTask,
    setActiveTask, toggleDataSource, sendMessage, setCurrentAgent
  }
})
