<script setup>
import { useDatabaseStore } from '@/stores/database'
const store = useDatabaseStore()
</script>

<template>
  <div class="kpi-grid">
    <div v-for="kpi in store.kpis" :key="kpi.label" class="kpi">
      <div class="kpi-ic" :style="{ background: kpi.iconBg, color: kpi.iconColor }">
        <!-- database icon -->
        <svg v-if="kpi.label === '总数据量'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>
        </svg>
        <svg v-else-if="kpi.label === '文档总数'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
        </svg>
        <svg v-else-if="kpi.label === '向量索引'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
          <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
        </svg>
        <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
        </svg>
      </div>
      <div class="kpi-l">{{ kpi.label }}</div>
      <div class="kpi-v">{{ kpi.value }} <span style="font-size:14px;color:var(--ink3)">{{ kpi.unit }}</span></div>
      <div class="kpi-trend" :class="kpi.trendDir">{{ kpi.trend }}</div>
    </div>
  </div>
</template>

<style scoped>
.kpi-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 14px; }
</style>
