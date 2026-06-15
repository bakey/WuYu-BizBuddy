import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'

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

  const taskHistory = ref([
    { id: 1, title: '2025 长三角无废城市政策对比分析', meta: '📜 政策解析 · 进行中',   pin: 'rd', pinned: true,  active: true  },
    { id: 2, title: '锂电池回收技术对标',               meta: '📊 企业对标 · 5天前',    pin: 'rd', pinned: true,  active: false },
    { id: 3, title: '知识图谱构建',                     meta: '🕸️ 图谱探索 · 7天前',   pin: 'gr', pinned: true,  active: false },
    { id: 4, title: '焚烧工艺数据采集与分析',           meta: '🏭 工艺指导 · 3天前',    pin: '',   pinned: false, active: false },
    { id: 5, title: '长三角遥感图像非法堆放识别',       meta: '🛰️ 遥感（V2）· 7天前',  pin: '',   pinned: false, active: false }
  ])

  const messages = ref([
    {
      id: 1, role: 'ai', sender: '政策解析专家', time: '14:30',
      content: '您好！我是<strong>政策解析专家</strong>，我自带 <strong>政策检索</strong>、<strong>条文比对</strong>、<strong>影响评估</strong>、<strong>合规清单</strong> 4 个技能。请描述您要研究的政策问题。'
    },
    {
      id: 2, role: 'user', time: '14:32',
      content: '帮我对比 2025 沪苏浙皖四地无废城市建设的政策差异，重点关注危废处置和资源化利用方面的扶持力度。'
    },
    {
      id: 3, role: 'ai', sender: '政策解析专家', time: '14:32',
      skillCall: '调用技能：政策检索 · 已检索 4 省 23 份文件',
      content: `<div style="font-weight:700;color:var(--ink);font-size:14px;margin-bottom:8px">2025 沪苏浙皖无废城市政策对比要点</div>
        <p style="margin-bottom:10px">综合分析最新政策文件后，四地在<strong>危废处置和资源化利用</strong>方面的扶持力度差异如下：</p>
        <ul style="padding-left:22px;line-height:1.85">
          <li><strong>上海</strong>：以单位 GDP 危废产生量考核，对电子废物拆解资质企业给予税收优惠</li>
          <li><strong>江苏</strong>：发布《无废园区建设导则》，省级专项资金 ¥3.2 亿支持 21 个园区试点</li>
          <li><strong>浙江</strong>：探索危废"点对点"利用试点，简化跨区转运审批</li>
          <li><strong>安徽</strong>：在合肥、芜湖建设区域危废协同处置中心</li>
        </ul>
        <p style="color:var(--ink3);font-size:12.5px;margin-top:10px">总体看，江苏在专项资金体量上领先，浙江在制度创新和审批优化上更激进。</p>`,
      citations: [
        { num: 1, label: '上海无废城市建设方案' },
        { num: 2, label: '江苏无废园区建设导则' },
        { num: 3, label: '浙江"点对点"利用通知' },
        { num: 4, label: '安徽危废协同处置规划' }
      ],
      actions: [
        { label: '生成对比矩阵', variant: 'green' },
        { label: '影响评估' },
        { label: '复制' }
      ]
    },
    {
      id: 4, role: 'user', time: '14:35',
      content: '生成横向对比矩阵，加上具体的资金额度。'
    },
    {
      id: 5, role: 'ai', sender: '政策解析专家', time: '14:35',
      thinking: '调用技能：条文比对 → 影响评估 · 正在生成对比矩阵...'
    }
  ])

  const citations = ref([
    { id: 1, title: '上海无废城市建设方案 (2024-2026)', meta: '[1] 政策法规库 · 95%', relevance: 'high' },
    { id: 2, title: '江苏无废园区建设导则',              meta: '[2] 政策法规库 · 92%', relevance: 'high' },
    { id: 3, title: '浙江危废"点对点"利用通知',         meta: '[3] 政策法规库 · 88%', relevance: 'high' },
    { id: 4, title: '安徽危废协同处置规划',              meta: '[4] 政策法规库 · 86%', relevance: 'high' },
    { id: 5, title: '国家无废城市试点中期评估报告',       meta: '[5] 学术论文 · 72%',   relevance: 'mid' },
    { id: 6, title: '长三角危废协同处置研究',            meta: '[6] 学术论文 · 68%',   relevance: 'mid' },
    { id: 7, title: '"无废园区"创建指南',               meta: '[7] 政策法规库 · 64%', relevance: 'mid' }
  ])

  let _nextId = messages.value.length + 1

  function setActiveTask(id) {
    taskHistory.value.forEach(t => { t.active = t.id === id })
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
      // eventType 必须跨 read() 持续：一个 SSE 事件的 `event:` 与 `data:`
      // 两行可能被网络分片拆到相邻 chunk，若每次 read 重置会丢事件类型导致丢字
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
              msgRefs = data.map((r, i) => ({ num: i + 1, label: r.source || `引用 ${i + 1}` }))
              citations.value = data.map((r, i) => ({
                id: i + 1,
                title: r.source || `文档片段 ${i + 1}`,
                meta: `[${i + 1}] 相似度 ${(r.score * 100).toFixed(0)}%`,
                relevance: r.score >= 0.85 ? 'high' : 'mid'
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
          // 流正常结束但一个 delta 都没收到（空回答）——替换掉 thinking 占位，
          // 否则气泡会永远卡在「正在检索…」
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

  return {
    currentAgent, dataSources, taskHistory, messages, citations,
    setActiveTask, toggleDataSource, sendMessage, setCurrentAgent
  }
})
