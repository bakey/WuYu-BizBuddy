import { defineStore } from 'pinia'
import { onMounted, ref, reactive, computed } from 'vue'

const DEFAULT_AGENT = {
  id: null,
  name: '政策解析专家',
  icon: '📜',
  bg: 'var(--primary-light)',
  color: 'var(--primary)',
  skillCount: 4,
  systemPrompt: null
}

export const useChatStore = defineStore('chat', () => {
  const currentAgent = reactive({ ...DEFAULT_AGENT })
  const availableAgents = ref([])
  const loadingAgents = ref(false)

  const dataSources = ref([
    { id: 1, name: '政策法规库', count: '12.4万', checked: true },
    { id: 2, name: '学术论文',   count: '86万',   checked: true },
    { id: 3, name: '企业数据',   count: '3.2万',  checked: false },
    { id: 4, name: '知识图谱',   count: '280万',  checked: false }
  ])

  const taskHistory = ref([])
  const loadingTasks = ref(false)

  const messages = ref([])
  const citations = ref([])

  let _nextId = 1

  const welcomeMessage = computed(() => {
    const skillsText = currentAgent.skills?.length
      ? currentAgent.skills.slice(0, 4).join('</strong>、<strong>')
      : ''
    return {
      id: _nextId++,
      role: 'ai',
      sender: currentAgent.name,
      time: new Date().toTimeString().slice(0, 5),
      content: `您好！我是<strong>${currentAgent.name}</strong>${skillsText ? `，我自带 <strong>${skillsText}</strong> ${currentAgent.skills.length} 个技能` : ''}。请描述您要研究的问题。`
    }
  })

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

  function _mapAgent(a) {
    return {
      id: a.id,
      name: a.name,
      agentType: a.agent_type || 'simple',
      icon: a.icon,
      bg: a.bg,
      color: a.color,
      desc: a.desc,
      skills: a.skills || [],
      users: a.users,
      rating: a.rating,
      featured: a.featured,
      category: a.category,
      tag: a.tag,
      source: a.source,
      systemPrompt: a.system_prompt,
      defaultTopK: a.default_top_k,
      retrievalMode: a.retrieval_mode
    }
  }

  async function loadAgents() {
    loadingAgents.value = true
    try {
      const items = await api('/agents')
      availableAgents.value = items.map(_mapAgent)
      if (availableAgents.value.length > 0 && !currentAgent.id) {
        const featured = availableAgents.value.find(a => a.featured)
        setCurrentAgent(featured || availableAgents.value[0])
      }
    } catch (err) {
      console.error('加载 Agent 失败', err)
    } finally {
      loadingAgents.value = false
    }
  }

  function setCurrentAgent(agent) {
    Object.assign(currentAgent, {
      id: agent.id,
      name: agent.name,
      agentType: agent.agentType || agent.agent_type || 'simple',
      icon: agent.icon,
      bg: agent.bg,
      color: agent.color,
      skillCount: agent.skills?.length || 0,
      skills: agent.skills || [],
      systemPrompt: agent.systemPrompt || agent.system_prompt || null,
      defaultTopK: agent.defaultTopK || agent.default_top_k || 5,
      retrievalMode: agent.retrievalMode || agent.retrieval_mode || 'basic_rag'
    })
    resetMessages()
  }

  function resetMessages() {
    messages.value = [welcomeMessage.value]
    citations.value = []
    _nextId = messages.value.length + 1
  }

  function _mapTask(t) {
    return {
      id: t.id,
      title: t.title,
      meta: t.meta || `${t.agent_name || currentAgent.name} · 刚刚`,
      pin: t.pin || '',
      pinned: t.pinned,
      active: t.active,
      agentName: t.agent_name,
      agentIcon: t.agent_icon,
      agentId: t.agent_id
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
      agent_icon: currentAgent.icon,
      agent_id: currentAgent.id
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
    if (updated.agentId) {
      const agent = availableAgents.value.find(a => a.id === updated.agentId)
      if (agent) setCurrentAgent(agent)
    }
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
    if (!currentAgent.id) {
      console.error('未选择 Agent')
      return
    }

    const now = new Date().toTimeString().slice(0, 5)
    messages.value.push({ id: _nextId++, role: 'user', time: now, content: text })

    const thinkId = _nextId++
    messages.value.push({
      id: thinkId, role: 'ai', sender: currentAgent.name,
      time: now, thinking: '正在检索相关资料…'
    })

    try {
      const isComposite = currentAgent.agentType === 'composite'
      const endpoint = isComposite
        ? `/api/v1/agents/${currentAgent.id}/execute/stream`
        : `/api/v1/agents/${currentAgent.id}/query/stream`

      const resp = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: text, top_k: currentAgent.defaultTopK || 5 })
      })

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let accText = ''
      let msgRefs = []
      let started = false
      let eventType = ''
      let trace = isComposite
        ? { plan: null, steps: [], reviews: [], revision: 0 }
        : null

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
                    content: accText, citations: [], actions: [], trace
                  }
                } else {
                  messages.value[idx].content = accText
                }
              }
            } else if (eventType === 'plan' && trace) {
              trace.plan = data
              const idx = messages.value.findIndex(m => m.id === thinkId)
              if (idx > -1) messages.value[idx].thinking = '正在制定执行计划…'
            } else if (eventType === 'step_start' && trace) {
              trace.steps.push({ ...data, status: 'running', summary: '' })
              const idx = messages.value.findIndex(m => m.id === thinkId)
              if (idx > -1) messages.value[idx].thinking = `正在执行：${data.action}…`
            } else if (eventType === 'step_complete' && trace) {
              const step = trace.steps.find(s => s.step_number === data.step_number)
              if (step) Object.assign(step, data)
              const idx = messages.value.findIndex(m => m.id === thinkId)
              if (idx > -1) messages.value[idx].thinking = `步骤 ${data.step_number} 完成`
            } else if (eventType === 'review' && trace) {
              trace.reviews.push(data)
            } else if (eventType === 'revision' && trace) {
              trace.revision = data.revision
              const idx = messages.value.findIndex(m => m.id === thinkId)
              if (idx > -1 && !started) messages.value[idx].thinking = '正在根据评审意见重新规划…'
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
            citations: msgRefs, actions: [], trace
          }
        } else {
          messages.value[idx].citations = msgRefs
          messages.value[idx].actions = [
            { label: '追问', variant: 'green' }, { label: '复制' }, { label: '导出' }
          ]
          messages.value[idx].trace = trace
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

  onMounted(() => {
    loadAgents().then(() => {
      resetMessages()
      loadTasks()
    })
  })

  return {
    currentAgent, availableAgents, loadingAgents,
    dataSources, taskHistory, messages, citations, loadingTasks,
    loadAgents, setCurrentAgent, resetMessages,
    loadTasks, createTask, activateTask, togglePinTask, deleteTask,
    setActiveTask, toggleDataSource, sendMessage
  }
})
