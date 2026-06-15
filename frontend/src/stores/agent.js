import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAgentStore = defineStore('agent', () => {
  const agents = ref([
    {
      id: 1, name: '政策解析专家', icon: '📜', bg: 'var(--primary-light)', color: 'var(--primary)',
      desc: '解读国/省/市三级固废政策，输出风险点、合规清单与执行要求。',
      skills: ['政策检索', '条文比对', '影响评估', '合规清单'],
      users: '1.2k', rating: 4.9, featured: true, category: '政策解析',
      tag: { label: '推荐', cls: 'tag-green' }
    },
    {
      id: 2, name: '工艺指导专家', icon: '🏭', bg: '#FEF3C7', color: 'var(--warn)',
      desc: '提供焚烧、填埋、资源化等核心工艺参数、排放预测与故障诊断建议。',
      skills: ['工艺参数', '排放预测', '故障诊断', '能耗分析', '+1'],
      users: '846', rating: 4.7, featured: false, category: '工艺技术'
    },
    {
      id: 3, name: '企业对标分析师', icon: '📊', bg: 'var(--purple-light)', color: 'var(--purple)',
      desc: '对比目标企业的经营、技术与专利布局，输出竞争情报与差距分析。',
      skills: ['企业画像', '技术对比', '专利矩阵', '行业排名'],
      users: '612', rating: 4.6, featured: false, category: '企业研究'
    },
    {
      id: 4, name: '图谱探索员', icon: '🕸️', bg: 'var(--info-light)', color: 'var(--info)',
      desc: '通过实体-关系路径探索行业知识网络与隐藏关联，自动生成图谱可视化。',
      skills: ['实体检索', '路径推理', '图谱可视化'],
      users: '418', rating: 4.5, featured: false, category: '图谱与关系'
    },
    {
      id: 5, name: 'DeepResearch', icon: '🔬', bg: 'var(--danger-light)', color: 'var(--danger)',
      desc: '多步推理 · 多源交叉验证 · 输出含引用链的研究报告，适合复杂选题。',
      skills: ['问题拆解', '多源检索', '交叉验证', '+3'],
      users: '928', rating: 4.8, featured: false, category: '深度研究',
      tag: { label: '深度', cls: 'tag-purple' }
    }
  ])

  const categories = ref([
    { label: '📦 全部',      count: 6, active: true  },
    { label: '📜 政策解析',  count: 1, active: false },
    { label: '🏭 工艺技术',  count: 1, active: false },
    { label: '📊 企业研究',  count: 1, active: false },
    { label: '🕸️ 图谱与关系', count: 1, active: false },
    { label: '🔬 深度研究',  count: 1, active: false },
    { label: '🛰️ 遥感（V2）', count: 0, active: false, disabled: true }
  ])

  const sources = ref([
    { label: '官方 Agent', count: 5, checked: true  },
    { label: '企业自建',   count: 2, checked: false },
    { label: '社区共享',   count: 12, checked: false }
  ])

  const favorites = ref([
    { name: '政策解析专家',   icon: '📜', uses: 23 },
    { name: '企业对标分析师', icon: '📊', uses: 8  },
    { name: 'DeepResearch',  icon: '🔬', uses: 3  }
  ])

  const searchQuery = ref('')
  const activeCategory = ref('📦 全部')

  const filteredAgents = computed(() => {
    let list = agents.value
    if (!activeCategory.value.includes('全部')) {
      const keyword = activeCategory.value.replace(/^.+?\s/, '')
      list = list.filter(a => a.category.includes(keyword))
    }
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.toLowerCase()
      list = list.filter(a => a.name.toLowerCase().includes(q) || a.desc.toLowerCase().includes(q))
    }
    return list
  })

  function setCategory(label) {
    activeCategory.value = label
    categories.value.forEach(c => { c.active = c.label === label })
  }

  function createAgent(data) {
    agents.value.push({
      id: Date.now(), ...data,
      users: '0', rating: 0, featured: false
    })
  }

  return { agents, categories, sources, favorites, searchQuery, activeCategory, filteredAgents, setCategory, createAgent }
})
