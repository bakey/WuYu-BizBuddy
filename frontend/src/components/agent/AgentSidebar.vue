<script setup>
import { useAgentStore } from '@/stores/agent'
const emit = defineEmits(['create'])
const agentStore = useAgentStore()

function onCategoryClick(cat) {
  if (!cat.disabled) agentStore.setCategory(cat.label)
}
</script>

<template>
  <aside class="left-sidebar">
    <div class="left-scroll">
      <button class="btn-primary" @click="emit('create')">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <path d="M5 12h14"/><path d="M12 5v14"/>
        </svg>
        自建 Agent
      </button>

      <!-- Category filter -->
      <div class="card">
        <div class="card-hdr">
          <div class="card-accent"></div>
          <span class="card-title">分类筛选</span>
        </div>
        <div class="card-body">
          <div class="chips" style="flex-direction:column;gap:4px">
            <div
              v-for="cat in agentStore.categories"
              :key="cat.label"
              class="chip"
              :class="{ active: cat.active, 'opacity-50': cat.disabled }"
              :style="{ textAlign: 'left', display: 'flex', justifyContent: 'space-between', width: '100%', padding: '8px 10px', opacity: cat.disabled ? 0.5 : 1 }"
              @click="onCategoryClick(cat)"
            >
              <span>{{ cat.label }}</span>
              <span style="color:var(--ink4)">{{ cat.count || '—' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Sources -->
      <div class="card">
        <div class="card-hdr">
          <div class="card-accent card-accent--blue"></div>
          <span class="card-title">Agent 来源</span>
        </div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:6px">
          <label v-for="s in agentStore.sources" :key="s.label" style="display:flex;align-items:center;gap:8px;font-size:12px;cursor:pointer">
            <input type="checkbox" v-model="s.checked" style="accent-color:var(--primary)">
            {{ s.label }}
            <span style="color:var(--ink4);margin-left:auto">{{ s.count }}</span>
          </label>
        </div>
      </div>

      <!-- Favorites -->
      <div class="card">
        <div class="card-hdr">
          <div class="card-accent card-accent--orange"></div>
          <span class="card-title">我的收藏</span>
          <span class="card-badge gray">{{ agentStore.favorites.length }}</span>
        </div>
        <div style="padding:8px 10px">
          <div v-for="f in agentStore.favorites" :key="f.name" class="hist-item">
            <span style="font-size:16px">{{ f.icon }}</span>
            <div class="hist-info">
              <div class="hist-q">{{ f.name }}</div>
              <div class="hist-meta">使用 {{ f.uses }} 次</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>
