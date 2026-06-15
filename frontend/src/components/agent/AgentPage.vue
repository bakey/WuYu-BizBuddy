<script setup>
import AgentSidebar from './AgentSidebar.vue'
import AgentGrid from './AgentGrid.vue'
import AgentCreateModal from './AgentCreateModal.vue'
import { ref } from 'vue'

const showCreateModal = ref(false)
</script>

<template>
  <div class="page-wrapper">
    <AgentSidebar @create="showCreateModal = true" />
    <div class="agent-main">
      <AgentGrid @create="showCreateModal = true" />
    </div>
    <AgentCreateModal :show="showCreateModal" @close="showCreateModal = false" />
  </div>
</template>

<style scoped>
.agent-main { flex: 1; min-width: 0; padding: 16px; background: var(--bg); display: flex; flex-direction: column; gap: 16px; overflow: hidden; }
</style>
