import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useIntegrationStore = defineStore('integration', () => {
  const dataSources = ref([
    { id: 1, icon: '🏛️', iconBg: 'var(--info-light)',   iconColor: 'var(--info)',   name: '国家危废产生申报系统',    desc: '生态环境部 · OAuth 2.0 · 3.4 万 条/日', status: 'ok',   statusLabel: '已激活',   freq: '实时', volume: '2.1 亿 条' },
    { id: 2, icon: '📊', iconBg: 'var(--info-light)',   iconColor: 'var(--info)',   name: '国家统计局 · 工业统计',    desc: 'REST API · 月度刷新 · 公开数据',        status: 'ok',   statusLabel: '已激活',   freq: '每月', volume: '86 万 行' },
    { id: 3, icon: '🗺️', iconBg: 'var(--info-light)',   iconColor: 'var(--info)',   name: '江苏省固废监管一张图',    desc: '省级开放平台 · 数据库直连 · WebSocket', status: 'ok',   statusLabel: '已激活',   freq: '实时', volume: '4.2 万 条/日' },
    { id: 4, icon: '🏢', iconBg: '#FEF3C7',             iconColor: 'var(--warn)',   name: '中节能集团 · SAP ERP',    desc: '企业内部 · OData · 私有 VPN',          status: 'ok',   statusLabel: '已激活',   freq: '每小时', volume: '3.8 GB' },
    { id: 5, icon: '🏭', iconBg: '#FEF3C7',             iconColor: 'var(--warn)',   name: '光大环境 · MES 生产系统', desc: '企业内部 · MQTT 消息流',               status: 'warn', statusLabel: '授权待审', freq: '实时', volume: '—' },
    { id: 6, icon: '🛃', iconBg: 'var(--danger-light)', iconColor: 'var(--danger)', name: '海关总署 · 进出口固废',   desc: 'REST API · 凭证已过期',                status: 'err',  statusLabel: '连接失败', freq: '每日', volume: '—' }
  ])

  const dataTypes = ref([
    { label: '🌐 全部',      count: 13, active: true  },
    { label: '🏛️ 政府平台',  count: 5,  active: false },
    { label: '🏢 企业系统',  count: 8,  active: false },
    { label: '🌍 第三方平台', count: 0,  active: false }
  ])

  const connectionTypes = ref([
    { label: 'REST API',  count: 8, checked: true  },
    { label: 'OAuth 2.0', count: 3, checked: true  },
    { label: '数据库直连', count: 2, checked: false },
    { label: 'MQTT 消息流', count: 1, checked: false }
  ])

  const connectionStatuses = ref([
    { label: '已激活', count: 10, color: 'var(--primary)', checked: true },
    { label: '待审核', count: 2,  color: 'var(--warn)',    checked: true },
    { label: '失败',   count: 1,  color: 'var(--danger)',  checked: true }
  ])

  const govBucket = ref({
    connected: 5, pending: 3, daily: '14.6万', successRate: '99.4%'
  })

  const entBucket = ref({
    connected: 8, configuring: 4, syncSize: '2.3 GB', tenants: 12
  })

  const wizard = ref({
    active: true,
    title: '🚀 新接入向导 · 国家危废产生申报系统',
    fillPct: 50,
    steps: [
      { label: '选择数据源', state: 'done'   },
      { label: '配置认证',   state: 'done'   },
      { label: '字段映射',   state: 'active' },
      { label: '连接测试',   state: ''       },
      { label: '上线发布',   state: ''       }
    ]
  })

  function removeSource(id) {
    const idx = dataSources.value.findIndex(s => s.id === id)
    if (idx > -1) dataSources.value.splice(idx, 1)
  }

  function dismissWizard() {
    wizard.value.active = false
  }

  return { dataSources, dataTypes, connectionTypes, connectionStatuses, govBucket, entBucket, wizard, removeSource, dismissWizard }
})
