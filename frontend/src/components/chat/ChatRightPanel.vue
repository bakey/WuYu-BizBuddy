<script setup>
import { useChatStore } from '@/stores/chat'
const chat = useChatStore()

const highCitations = () => chat.citations.filter(c => c.relevance === 'high')
const midCitations  = () => chat.citations.filter(c => c.relevance === 'mid')
</script>

<template>
  <aside class="right-panel">
    <div class="right-panel-hdr">
      <span class="right-panel-title">本次引用</span>
      <span class="card-badge">{{ chat.citations.length }}</span>
    </div>
    <div class="right-panel-body">
      <div class="hist-group-label">高相关</div>
      <div
        v-for="c in highCitations()"
        :key="c.id"
        class="hist-item"
      >
        <span class="hist-pin gr"></span>
        <div class="hist-info">
          <div class="hist-q">{{ c.title }}</div>
          <div class="hist-meta">{{ c.meta }}</div>
        </div>
      </div>
      <div class="hist-group-label">中相关</div>
      <div
        v-for="c in midCitations()"
        :key="c.id"
        class="hist-item"
      >
        <span class="hist-pin"></span>
        <div class="hist-info">
          <div class="hist-q">{{ c.title }}</div>
          <div class="hist-meta">{{ c.meta }}</div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.right-panel {
  width: 280px; flex-shrink: 0; display: flex; flex-direction: column;
  background: var(--surface); border-radius: var(--radius-lg);
  border: 1px solid var(--line); box-shadow: var(--shadow-card); overflow: hidden;
}
.right-panel-hdr {
  display: flex; align-items: center; justify-content: space-between;
  height: 52px; padding: 0 14px; border-bottom: 1px solid var(--line); flex-shrink: 0;
}
.right-panel-title { font-size: 13px; font-weight: 700; color: var(--ink); }
.right-panel-body  { flex: 1; overflow-y: auto; padding: 8px; }
</style>
