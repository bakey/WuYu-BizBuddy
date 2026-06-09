<script setup>
import { useIntegrationStore } from '@/stores/integration'
const emit = defineEmits(['add'])
const store = useIntegrationStore()

function onTypeClick(type) {
  store.dataTypes.forEach(t => { t.active = t.label === type.label })
}
</script>

<template>
  <aside class="left-sidebar">
    <div class="left-scroll">
      <button class="btn-primary" @click="emit('add')">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <path d="M5 12h14"/><path d="M12 5v14"/>
        </svg>
        新增数据源
      </button>

      <!-- Data type -->
      <div class="card">
        <div class="card-hdr"><div class="card-accent"></div><span class="card-title">数据类型</span></div>
        <div class="card-body">
          <div class="chips" style="flex-direction:column;gap:4px">
            <div
              v-for="t in store.dataTypes"
              :key="t.label"
              class="chip"
              :class="{ active: t.active }"
              :style="{ textAlign:'left', display:'flex', justifyContent:'space-between', width:'100%', padding:'8px 10px' }"
              @click="onTypeClick(t)"
            >
              <span>{{ t.label }}</span>
              <span style="color:var(--ink4)">{{ t.count }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Connection type -->
      <div class="card">
        <div class="card-hdr"><div class="card-accent card-accent--blue"></div><span class="card-title">接入方式</span></div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:6px">
          <label v-for="t in store.connectionTypes" :key="t.label" style="display:flex;align-items:center;gap:8px;font-size:12px;cursor:pointer">
            <input type="checkbox" v-model="t.checked" style="accent-color:var(--primary)">
            {{ t.label }}
            <span style="color:var(--ink4);margin-left:auto">{{ t.count }}</span>
          </label>
        </div>
      </div>

      <!-- Status -->
      <div class="card">
        <div class="card-hdr"><div class="card-accent card-accent--orange"></div><span class="card-title">连接状态</span></div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:6px">
          <label v-for="s in store.connectionStatuses" :key="s.label" style="display:flex;align-items:center;gap:8px;font-size:12px;cursor:pointer">
            <input type="checkbox" v-model="s.checked" style="accent-color:var(--primary)">
            <span class="st-dot" :style="{ color: s.color }"></span>
            {{ s.label }}
            <span style="color:var(--ink4);margin-left:auto">{{ s.count }}</span>
          </label>
        </div>
      </div>
    </div>
  </aside>
</template>
