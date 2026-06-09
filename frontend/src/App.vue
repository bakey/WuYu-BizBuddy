<script setup>
import { useAppStore } from '@/stores/app'
import AppHeader from '@/components/common/AppHeader.vue'
import AppToast from '@/components/common/AppToast.vue'
import ChatPage from '@/components/chat/ChatPage.vue'
import AgentPage from '@/components/agent/AgentPage.vue'
import IntegrationPage from '@/components/integration/IntegrationPage.vue'
import DatabasePage from '@/components/database/DatabasePage.vue'
import KnowledgePage from '@/components/knowledge/KnowledgePage.vue'

const appStore = useAppStore()
</script>

<template>
  <div class="app">
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
