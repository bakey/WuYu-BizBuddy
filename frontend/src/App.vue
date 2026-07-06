<script setup>
import { onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'
import AppHeader from '@/components/common/AppHeader.vue'
import AppToast from '@/components/common/AppToast.vue'
import ChatPage from '@/components/chat/ChatPage.vue'
import AgentPage from '@/components/agent/AgentPage.vue'
import IntegrationPage from '@/components/integration/IntegrationPage.vue'
import DatabasePage from '@/components/database/DatabasePage.vue'
import KnowledgePage from '@/components/knowledge/KnowledgePage.vue'

const appStore = useAppStore()
const userStore = useUserStore()

// 未登录会立刻 redirect 到 rswaste 登录页；登录成功后回跳带 token 回来。
onMounted(() => { userStore.boot() })
</script>

<template>
  <div v-if="!userStore.ready" class="app-boot">
    <div class="boot-mask">
      <div class="boot-spinner"></div>
      <div class="boot-text">正在验证登录状态…</div>
    </div>
  </div>
  <div v-else class="app">
    <AppHeader />
    <div class="content">
      <ChatPage v-show="appStore.activeTab === 'chat'" />
      <AgentPage v-show="appStore.activeTab === 'agent'" />
      <IntegrationPage v-show="appStore.activeTab === 'integ'" />
      <DatabasePage v-show="appStore.activeTab === 'db'" />
      <KnowledgePage v-show="appStore.activeTab === 'kb'" />
    </div>
    <AppToast />
  </div>
</template>

<style scoped>
.app-boot { min-height: 100vh; display: grid; place-items: center; background: var(--surface); }
.boot-mask { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.boot-spinner {
  width: 28px; height: 28px; border-radius: 50%;
  border: 3px solid var(--line); border-top-color: var(--primary);
  animation: spin 1s linear infinite;
}
.boot-text { font-size: 13px; color: var(--ink3); }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
