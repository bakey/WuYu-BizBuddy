<script setup>
import DatabaseSidebar  from './DatabaseSidebar.vue'
import KpiGrid          from './KpiGrid.vue'
import BarChart         from './BarChart.vue'
import GovernanceTasks  from './GovernanceTasks.vue'
import DatabaseTable    from './DatabaseTable.vue'
import { useToast }     from '@/composables/useToast'
import { useDatabaseStore } from '@/stores/database'

const store  = useDatabaseStore()
const { toast } = useToast()

function onTriggerClean() {
  store.triggerCleanAll()
  toast('已派发全量清洗任务（演示）', 'ok')
}
</script>

<template>
  <div class="page-wrapper">
    <DatabaseSidebar />
    <div class="db-main">
      <div class="page-hdr">
        <div>
          <h2>云数据库 · 总览与治理</h2>
          <div class="page-hdr-sub">全部数据库的健康度、容量、索引状态一眼可见。当存在数据质量问题时自动派发清洗任务。</div>
        </div>
        <div class="row">
          <button class="btn-secondary" @click="toast('报告已导出', 'ok')">导出报告</button>
          <button class="btn-secondary" @click="toast('请配置新库参数', 'info')">+ 新建库</button>
        </div>
      </div>

      <KpiGrid />

      <div class="stats-grid">
        <BarChart />
        <GovernanceTasks />
      </div>

      <DatabaseTable />
    </div>
  </div>
</template>

<style scoped>
.db-main    { flex: 1; min-width: 0; padding: 16px; background: var(--bg); display: flex; flex-direction: column; gap: 14px; overflow-y: auto; }
.stats-grid { display: grid; grid-template-columns: 1.6fr 1fr; gap: 14px; }
</style>
