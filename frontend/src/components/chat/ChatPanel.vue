<script setup>
import { computed } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useToast } from '@/composables/useToast'
import ChatMessage from './ChatMessage.vue'
import ChatInputBar from './ChatInputBar.vue'

const chat = useChatStore()
const { toast } = useToast()

const activeTask = computed(() => chat.taskHistory.find(t => t.active))
</script>

<template>
  <div class="chat-panel">
    <!-- Header -->
    <div class="chat-panel-hdr">
      <div class="chat-panel-hdr-l">
        <span class="pill-dot"></span>
        <span class="chat-panel-title">{{ activeTask?.title ?? '新对话' }}</span>
        <span class="pill">📜 {{ chat.currentAgent.name }}</span>
      </div>
      <div class="row">
        <button class="btn-secondary" @click="toast('分享链接已复制', 'ok')">
          <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round">
            <circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>
            <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>
            <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>
          </svg>分享
        </button>
        <button class="btn-secondary" @click="toast('已导出为 PDF', 'ok')">
          <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
          </svg>导出
        </button>
      </div>
    </div>

    <!-- Messages -->
    <div class="chat-messages" ref="messagesEl">
      <ChatMessage
        v-for="msg in chat.messages"
        :key="msg.id"
        :message="msg"
      />
    </div>

    <ChatInputBar />
  </div>
</template>

<style scoped>
.chat-panel {
  flex: 1; min-width: 0; min-height: 0;
  display: flex; flex-direction: column;
  background: var(--surface); border-radius: var(--radius-lg);
  border: 1px solid var(--line); box-shadow: var(--shadow-card); overflow: hidden;
}
.chat-panel-hdr {
  display: flex; align-items: center; justify-content: space-between;
  height: 52px; padding: 0 18px; border-bottom: 1px solid var(--line); flex-shrink: 0;
}
.chat-panel-hdr-l { display: flex; align-items: center; gap: 10px; }
.chat-panel-title { font-size: 14px; font-weight: 700; color: var(--ink); }
.chat-messages {
  flex: 1; overflow-y: auto; padding: 20px 28px;
  display: flex; flex-direction: column; gap: 18px;
}
</style>
