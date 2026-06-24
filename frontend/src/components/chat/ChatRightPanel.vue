<script setup>
import { useChatStore } from '@/stores/chat'
import { useCitationPreview } from '@/composables/useCitationPreview'

const chat = useChatStore()
const { openPreview } = useCitationPreview()

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
      <div v-if="!chat.citations.length" class="cite-empty">
        提问后，这里会显示本次回答引用的资料来源，点击可预览原文。
      </div>
      <template v-else>
        <template v-if="highCitations().length">
          <div class="hist-group-label">高相关</div>
          <div
            v-for="c in highCitations()"
            :key="c.id"
            class="hist-item"
            style="cursor:pointer"
            title="点击预览引用原文"
            @click="openPreview(c)"
          >
            <span class="hist-pin gr"></span>
            <div class="hist-info">
              <div class="hist-q">{{ c.title }}</div>
              <div class="hist-meta">{{ c.meta }}</div>
            </div>
          </div>
        </template>
        <template v-if="midCitations().length">
          <div class="hist-group-label">中相关</div>
          <div
            v-for="c in midCitations()"
            :key="c.id"
            class="hist-item"
            style="cursor:pointer"
            title="点击预览引用原文"
            @click="openPreview(c)"
          >
            <span class="hist-pin"></span>
            <div class="hist-info">
              <div class="hist-q">{{ c.title }}</div>
              <div class="hist-meta">{{ c.meta }}</div>
            </div>
          </div>
        </template>
      </template>
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
.cite-empty {
  padding: 20px 14px; font-size: 12px; color: var(--ink4); line-height: 1.7; text-align: center;
}
</style>
