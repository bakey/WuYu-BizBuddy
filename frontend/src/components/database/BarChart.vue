<script setup>
import { useDatabaseStore } from '@/stores/database'
const store = useDatabaseStore()
</script>

<template>
  <div class="card">
    <div class="card-hdr">
      <div class="card-accent"></div>
      <span class="card-title">每日入库数据量（万条）</span>
    </div>
    <div class="card-body" style="padding:18px">
      <div class="bars">
        <div
          v-for="(val, i) in store.currentBarData.values"
          :key="i"
          class="bar-col"
        >
          <div class="bar-fill" :style="{ height: val + '%' }"></div>
          <div class="bar-l">{{ store.currentBarData.labels[i] }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bars { display: flex; align-items: flex-end; gap: 12px; height: 180px; padding: 4px 0; }
.bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; gap: 6px; height: 100%; }
.bar-fill { width: 100%; max-width: 28px; background: linear-gradient(180deg,#10B981,#059669); border-radius: 6px 6px 0 0; transition: height .3s ease; cursor: pointer; }
.bar-fill:hover { opacity: .85; }
.bar-l { font-size: 10.5px; color: var(--ink4); }
</style>
