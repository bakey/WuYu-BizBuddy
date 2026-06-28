<script setup>
import { computed } from 'vue'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

const beLabel = computed(() => ({
  checking: '检测中', online: '后端在线', offline: '后端离线'
}[appStore.backendStatus] || ''))

const TABS = [
  { key: 'chat',  label: '智能问答', badge: null },
  { key: 'agent', label: 'Agent 中心', badge: 'NEW' },
  { key: 'integ', label: '数据接入', badge: null },
  { key: 'db',    label: '云数据库', badge: null },
  { key: 'kb',    label: '企业知识库', badge: null }
]
</script>

<template>
  <header class="header">
    <!-- Brand -->
    <div class="brand">
      <div class="brand-icon">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2L9.5 8.5 3 11l6.5 2.5L12 20l2.5-6.5L21 11l-6.5-2.5L12 2z"/>
        </svg>
      </div>
      <span class="brand-name">无隅云数据库<span class="brand-v">v2.0</span></span>
    </div>

    <!-- Tabs -->
    <nav class="tabs">
      <button
        v-for="tab in TABS"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: appStore.activeTab === tab.key }"
        @click="appStore.setTab(tab.key)"
      >
        <span class="tab-badge" v-if="tab.badge">{{ tab.badge }}</span>
        {{ tab.label }}
      </button>
    </nav>

    <!-- Right actions -->
    <div class="header-right">
      <span class="be-status" :class="appStore.backendStatus" :title="`后端 /api/v1/health：${beLabel}`">
        <span class="be-dot"></span>{{ beLabel }}
      </span>
      <button class="icon-btn" title="搜索">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
        </svg>
      </button>
      <button class="icon-btn" title="通知">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
      </button>
      <button class="icon-btn" title="设置">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </button>
      <button class="avatar-btn">吴</button>
    </div>
  </header>
</template>

<style scoped>
.be-status {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 0 10px; height: 28px; border-radius: 14px;
  font-size: 11px; font-weight: 600; white-space: nowrap;
  border: 1px solid var(--line); background: var(--surface2); color: var(--ink3);
}
.be-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--warn); }
.be-status.online  { background: var(--primary-light); border-color: var(--primary-border); color: var(--primary); }
.be-status.online .be-dot  { background: var(--primary); box-shadow: 0 0 5px rgba(16,185,129,.6); }
.be-status.offline { background: var(--danger-light); border-color: #FCA5A5; color: var(--danger); }
.be-status.offline .be-dot { background: var(--danger); }
.be-status.checking .be-dot { background: var(--warn); }
</style>
