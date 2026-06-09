import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const BAR_DATA = {
  '7 天':  { values: [62,50,78,88,46,72,94], labels: ['5/2','5/3','5/4','5/5','5/6','5/7','5/8'] },
  '30 天': { values: [42,55,68,72,60,80,75,85,90,68,72,88,95,82,76,84,88,92,70,65,78,84,90,72,80,88,94,68,75,86], labels: Array.from({length:30}, (_,i) => `4/${10+i}`) },
  '90 天': { values: Array.from({length:30}, (_,i) => 30 + Math.round(50 * Math.sin(i/4) + 20)), labels: Array.from({length:30}, (_,i) => `周${i+1}`) }
}

export const useDatabaseStore = defineStore('database', () => {
  const timeRange = ref('7 天')

  const currentBarData = computed(() => {
    const data = BAR_DATA[timeRange.value] || BAR_DATA['7 天']
    const step = Math.max(1, Math.floor(data.values.length / 15))
    return {
      values: data.values.filter((_, i) => i % step === 0).slice(0, 15),
      labels: data.labels.filter((_, i) => i % step === 0).slice(0, 15)
    }
  })

  const kpis = ref([
    { label: '总数据量', value: '3.8',  unit: 'TB',         trend: '▲ 12.4%',   trendDir: 'up',   iconBg: 'var(--primary-light)', iconColor: 'var(--primary)' },
    { label: '文档总数', value: '986',  unit: '万',         trend: '▲ 6.8%',    trendDir: 'up',   iconBg: 'var(--info-light)',    iconColor: 'var(--info)'    },
    { label: '向量索引', value: '12',   unit: 'collection', trend: '▲ 2 个新增', trendDir: 'up',   iconBg: 'var(--purple-light)', iconColor: 'var(--purple)'  },
    { label: '健康度',   value: '98.6', unit: '%',          trend: '▼ 0.3%',    trendDir: 'down', iconBg: 'var(--warn-light)',   iconColor: 'var(--warn)'    }
  ])

  const databases = ref([
    { id: 1, icon: '📑', iconBg: 'var(--info-light)',    iconColor: 'var(--info)',    name: 'policy_db',        meta: '政策法规 · 国/省/市三级',  records: '12.4 万',  size: '3.2 GB',  indexStatus: 'ok',   indexLabel: '已索引',     health: 99, healthCls: 'ok'   },
    { id: 2, icon: '📄', iconBg: 'var(--primary-light)', iconColor: 'var(--primary)', name: 'paper_db',         meta: '学术论文 · 中英文混合',    records: '86.2 万',  size: '512 GB',  indexStatus: 'warn', indexLabel: '增量重建中',  health: 96, healthCls: 'ok'   },
    { id: 3, icon: '🏭', iconBg: 'var(--warn-light)',    iconColor: 'var(--warn)',    name: 'enterprise_db',    meta: '企业基本信息 + 经营数据',  records: '3.2 万',   size: '1.6 GB',  indexStatus: 'ok',   indexLabel: '已索引',     health: 78, healthCls: 'warn' },
    { id: 4, icon: '🕸️', iconBg: 'var(--purple-light)', iconColor: 'var(--purple)',  name: 'graph_db',         meta: 'Neo4j · 实体关系图谱',     records: '280 万',   size: '42 GB',   indexStatus: 'ok',   indexLabel: '已索引',     health: 94, healthCls: 'ok'   },
    { id: 5, icon: '🔥', iconBg: 'var(--danger-light)', iconColor: 'var(--danger)',  name: 'process_db',       meta: '焚烧工艺时序数据',         records: '9.6 亿 点', size: '2.1 TB',  indexStatus: 'warn', indexLabel: '索引中 76%', health: 84, healthCls: 'warn' },
    { id: 6, icon: '🛰️', iconBg: 'var(--surface2)',     iconColor: 'var(--ink4)',   name: 'remote_sensing_db', meta: '遥感影像 · V2.0 规划',    records: '—',        size: '—',       indexStatus: 'idle', indexLabel: '未启用',     health: 0,  healthCls: '',    disabled: true }
  ])

  const dbCategories = ref([
    { id: 1, icon: '📑', iconColor: 'var(--info)',    name: 'policy_db',         meta: '12.4 万 · 3.2 GB', active: true  },
    { id: 2, icon: '📄', iconColor: 'var(--primary)', name: 'paper_db',          meta: '86 万 · 512 GB',   active: false },
    { id: 3, icon: '🏭', iconColor: 'var(--warn)',    name: 'enterprise_db',     meta: '3.2 万 · 1.6 GB',  active: false },
    { id: 4, icon: '🕸️', iconColor: 'var(--purple)', name: 'graph_db',          meta: '280 万 · 42 GB',   active: false },
    { id: 5, icon: '🔥', iconColor: 'var(--danger)', name: 'process_db',        meta: '9.6 亿 · 2.1 TB',  active: false },
    { id: 6, icon: '🛰️', iconColor: 'var(--ink4)',   name: 'remote_sensing_db', meta: 'V2.0 规划',         active: false, disabled: true }
  ])

  const governanceTasks = ref([
    { id: 1, icon: '🔁', iconBg: 'var(--info-light)',    iconColor: 'var(--info)',    title: '企业实体去重',          desc: '合并相似度 ≥ 95% 的企业记录',         progress: 64  },
    { id: 2, icon: '⚠️', iconBg: 'var(--warn-light)',    iconColor: 'var(--warn)',    title: '缺失值检测',            desc: '12 个表存在 ≥ 5% 缺失字段',          progress: 32  },
    { id: 3, icon: '✅', iconBg: 'var(--primary-light)', iconColor: 'var(--primary)', title: '字段标准化',            desc: '行业代码已统一为 GB/T 4754-2017',   progress: 100 },
    { id: 4, icon: '🚨', iconBg: 'var(--danger-light)',  iconColor: 'var(--danger)',  title: '异常值告警 · 排放数据', desc: '检测到 23 条数据偏离 3σ，待人工复核', progress: null }
  ])

  const healthFilters = ref([
    { label: '🟢 优 (≥95%)',  count: 3, checked: true  },
    { label: '🟡 良 (80-94%)', count: 2, checked: true  },
    { label: '🔴 异常 (<80%)', count: 0, checked: false }
  ])

  const activeDbId = ref(1)

  function setTimeRange(range) {
    timeRange.value = range
  }

  function setActiveDb(id) {
    dbCategories.value.forEach(c => { c.active = c.id === id })
    activeDbId.value = id
  }

  function triggerCleanAll() {
    const task = governanceTasks.value[0]
    if (task && task.progress !== null && task.progress < 100) {
      const interval = setInterval(() => {
        if (task.progress >= 100) { clearInterval(interval); return }
        task.progress = Math.min(100, task.progress + 4)
      }, 200)
    }
  }

  return {
    timeRange, currentBarData, kpis, databases, dbCategories,
    governanceTasks, healthFilters, activeDbId,
    setTimeRange, setActiveDb, triggerCleanAll
  }
})
