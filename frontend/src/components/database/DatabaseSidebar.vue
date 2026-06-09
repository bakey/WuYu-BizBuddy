<script setup>
import { useDatabaseStore } from '@/stores/database'
import { useToast }         from '@/composables/useToast'

const store  = useDatabaseStore()
const { toast } = useToast()

function onDbClick(cat) {
  if (cat.disabled) return
  store.setActiveDb(cat.id)
  toast(`已聚焦 · ${cat.name}`, 'info')
}

function onTriggerClean() {
  store.triggerCleanAll()
  toast('已派发全量清洗任务（演示）', 'ok')
}
</script>

<template>
  <aside class="left-sidebar">
    <div class="left-scroll">
      <button class="btn-primary" @click="onTriggerClean">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
        </svg>
        触发全量清洗
      </button>

      <!-- DB categories -->
      <div class="card">
        <div class="card-hdr">
          <div class="card-accent"></div>
          <span class="card-title">数据库分类</span>
          <span class="card-badge gray">{{ store.dbCategories.length }}</span>
        </div>
        <div style="padding:6px 10px">
          <div
            v-for="cat in store.dbCategories"
            :key="cat.id"
            class="hist-item"
            :class="{ active: cat.active }"
            :style="{ opacity: cat.disabled ? 0.5 : 1 }"
            @click="onDbClick(cat)"
          >
            <span :style="{ color: cat.iconColor, fontSize: '14px' }">{{ cat.icon }}</span>
            <div class="hist-info">
              <div class="hist-q">{{ cat.name }}</div>
              <div class="hist-meta">{{ cat.meta }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Health filter -->
      <div class="card">
        <div class="card-hdr"><div class="card-accent card-accent--orange"></div><span class="card-title">健康度</span></div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:6px">
          <label v-for="f in store.healthFilters" :key="f.label" style="display:flex;align-items:center;gap:8px;font-size:12px;cursor:pointer">
            <input type="checkbox" v-model="f.checked" style="accent-color:var(--primary)">
            {{ f.label }}
            <span style="color:var(--ink4);margin-left:auto">{{ f.count }}</span>
          </label>
        </div>
      </div>

      <!-- Time range -->
      <div class="card">
        <div class="card-hdr"><div class="card-accent card-accent--blue"></div><span class="card-title">时间范围</span></div>
        <div class="card-body">
          <div class="row" style="gap:6px">
            <button
              v-for="r in ['7 天','30 天','90 天']"
              :key="r"
              class="btn-mode"
              :class="{ active: store.timeRange === r }"
              @click="store.setTimeRange(r)"
            >{{ r }}</button>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>
