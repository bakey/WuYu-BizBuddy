import { defineStore } from 'pinia'
import { ref, computed, onMounted } from 'vue'
import { apiJson } from '@/utils/api'

const CATEGORY_META = [
  { key: '全部', icon: '📦', disabled: false },
  { key: '政策解析', icon: '📜', disabled: false },
  { key: '工艺技术', icon: '🏭', disabled: false },
  { key: '企业研究', icon: '📊', disabled: false },
  { key: '图谱与关系', icon: '🕸️', disabled: false },
  { key: '深度研究', icon: '🔬', disabled: false },
  { key: '遥感（V2）', icon: '🛰️', disabled: true }
]

const SOURCE_OPTIONS = [
  { label: '官方 Agent', checked: true },
  { label: '企业自建', checked: false },
  { label: '社区共享', checked: false }
]

export const useAgentStore = defineStore('agent', () => {
  const agents = ref([])
  const loading = ref(false)
  const searchQuery = ref('')
  const activeCategory = ref('📦 全部')
  const sources = ref(SOURCE_OPTIONS.map(s => ({ ...s, count: 0 })))

  const favorites = ref([
    { name: '政策解析专家', icon: '📜', uses: 23 },
    { name: '企业对标分析师', icon: '📊', uses: 8 },
    { name: 'DeepResearch', icon: '🔬', uses: 3 }
  ])

  const api = apiJson

  function _mapAgent(a) {
    return {
      id: a.id,
      name: a.name,
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
      retrievalMode: a.retrieval_mode,
      industrySkillId: a.industry_skill_id
    }
  }

  async function loadAgents(params = {}) {
    loading.value = true
    try {
      const qs = new URLSearchParams()
      if (params.category) qs.set('category', params.category)
      if (params.source) qs.set('source', params.source)
      if (params.search) qs.set('search', params.search)
      const items = await api(`/agents?${qs.toString()}`)
      agents.value = items.map(_mapAgent)

      const counts = {}
      agents.value.forEach(a => {
        counts[a.source] = (counts[a.source] || 0) + 1
      })
      sources.value = SOURCE_OPTIONS.map(s => ({
        ...s,
        count: counts[s.label] || 0
      }))
    } catch (err) {
      console.error('加载 Agent 失败', err)
    } finally {
      loading.value = false
    }
  }

  const categories = computed(() => {
    const counts = {}
    agents.value.forEach(a => {
      counts[a.category] = (counts[a.category] || 0) + 1
    })
    return CATEGORY_META.map(meta => {
      const label = `${meta.icon} ${meta.key}`
      const count = meta.key === '全部'
        ? agents.value.length
        : (counts[meta.key] || 0)
      return {
        label,
        count: count || '—',
        active: label === activeCategory.value,
        disabled: meta.disabled
      }
    })
  })

  const filteredAgents = computed(() => {
    let list = agents.value
    if (!activeCategory.value.includes('全部')) {
      const keyword = activeCategory.value.replace(/^.+?\s/, '')
      list = list.filter(a => a.category.includes(keyword))
    }
    const checkedSources = sources.value.filter(s => s.checked).map(s => s.label)
    if (checkedSources.length > 0) {
      list = list.filter(a => checkedSources.includes(a.source))
    }
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase()
      list = list.filter(a =>
        a.name.toLowerCase().includes(q) || a.desc.toLowerCase().includes(q)
      )
    }
    return list
  })

  function setCategory(label) {
    activeCategory.value = label
  }

  async function createAgent(data) {
    const payload = {
      name: data.name,
      icon: data.icon || '🤖',
      bg: data.bg || 'var(--surface2)',
      color: data.color || 'var(--ink)',
      desc: data.desc || '',
      skills: data.skills || [],
      users: '0',
      rating: 0,
      featured: false,
      category: data.category || '未分类',
      source: data.source || '企业自建'
    }
    const a = await api('/agents', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
    agents.value.push(_mapAgent(a))
    return _mapAgent(a)
  }

  onMounted(() => {
    loadAgents()
  })

  return {
    agents, loading, searchQuery, activeCategory, sources, favorites,
    categories, filteredAgents,
    loadAgents, setCategory, createAgent
  }
})
