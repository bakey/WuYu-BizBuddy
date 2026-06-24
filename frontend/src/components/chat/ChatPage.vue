<script setup>
import ChatSidebar from './ChatSidebar.vue'
import ChatPanel from './ChatPanel.vue'
import ChatRightPanel from './ChatRightPanel.vue'
import CitationPreviewModal from './CitationPreviewModal.vue'
</script>

<template>
  <div class="page-wrapper">
    <ChatSidebar />
    <div class="chat-main">
      <div class="chat-wrap">
        <ChatPanel />
        <ChatRightPanel />
      </div>
    </div>
    <CitationPreviewModal />
  </div>
</template>

<style scoped>
.chat-main { flex: 1; min-width: 0; background: var(--bg); display: flex; flex-direction: column; }
.chat-wrap  { flex: 1; min-height: 0; display: flex; gap: 12px; padding: 12px; }
</style>
