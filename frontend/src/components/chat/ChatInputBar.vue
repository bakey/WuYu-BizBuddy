<script setup>
import { ref } from 'vue'
import { useChatStore } from '@/stores/chat'

const chat = useChatStore()
const inputText = ref('')

function doSend() {
  const txt = inputText.value.trim()
  if (!txt) return
  chat.sendMessage(txt)
  inputText.value = ''
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    doSend()
  }
}
</script>

<template>
  <div class="chat-input-bar">
    <div class="chat-input-pills">
      <span class="chat-input-pill active">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/>
        </svg>
        {{ chat.currentAgent.name }}
      </span>
      <span class="chat-input-pill">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
        </svg>
        {{ chat.dataSources.filter(d => d.checked).length }} 数据源
      </span>
    </div>

    <div class="chat-input-field">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="color:var(--ink4)">
        <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 17.93 8.8l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
      </svg>
      <input
        type="text"
        v-model="inputText"
        placeholder="继续对话，或输入新问题..."
        @keydown="onKeydown"
      />
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="color:var(--ink4)">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
        <line x1="12" y1="19" x2="12" y2="23"/>
      </svg>
    </div>

    <button class="send-btn" @click="doSend">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="22" y1="2" x2="11" y2="13"/>
        <polygon points="22 2 15 22 11 13 2 9 22 2"/>
      </svg>
    </button>
  </div>
</template>

<style scoped>
.chat-input-bar {
  display: flex; align-items: center; gap: 10px;
  height: 76px; padding: 0 18px;
  border-top: 1px solid var(--line); flex-shrink: 0;
  background: var(--surface);
}
.chat-input-pills { display: flex; align-items: center; gap: 6px; }
.chat-input-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 10px; border-radius: 6px;
  border: 1px solid var(--line); background: var(--surface2);
  font-size: 11.5px; font-weight: 500; color: var(--ink2);
  cursor: pointer; transition: all .15s;
}
.chat-input-pill.active { background: var(--primary-light); border-color: var(--primary-border); color: var(--primary); }
.chat-input-field {
  flex: 1; display: flex; align-items: center; gap: 8px;
  height: 46px; background: var(--surface2); border: 1px solid var(--line);
  border-radius: 10px; padding: 0 14px;
}
.chat-input-field input { flex: 1; border: 0; background: transparent; outline: 0; font-size: 13px; color: var(--ink); }
.chat-input-field input::placeholder { color: var(--ink4); }
.send-btn {
  width: 46px; height: 46px; border-radius: 10px;
  background: var(--primary); border: 0; color: #fff;
  display: grid; place-items: center; cursor: pointer;
  box-shadow: 0 3px 10px rgba(5,150,105,.3); transition: background .15s;
}
.send-btn:hover { background: var(--primary-mid); }
</style>
