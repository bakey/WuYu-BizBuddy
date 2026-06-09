<script setup>
import { useAgentStore } from '@/stores/agent'
import { useAppStore }   from '@/stores/app'
import { useChatStore }  from '@/stores/chat'
import { useToast }      from '@/composables/useToast'
import AgentCard from './AgentCard.vue'

const emit = defineEmits(['create'])
const agentStore = useAgentStore()
const appStore   = useAppStore()
const chatStore  = useChatStore()
const { toast }  = useToast()

function onUse(agent) {
  chatStore.setCurrentAgent({
    name: agent.name,
    icon: agent.icon,
    bg: agent.bg,
    color: agent.color,
    skillCount: agent.skills.length
  })
  appStore.setTab('chat')
  toast(`已切换到 Agent · ${agent.name}`, 'ok')
}
</script>

<template>
  <div class="page-hdr">
    <div>
      <h2>Agent 中心</h2>
      <div class="page-hdr-sub">选择一个专家 Agent 开始任务，每个 Agent 自带专属技能包，支持自由组合 / 系统推荐 / 自建。</div>
    </div>
    <div class="row">
      <div class="row" style="background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:0 10px;height:34px;width:240px">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--ink4)">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
        </svg>
        <input v-model="agentStore.searchQuery" style="border:0;outline:0;flex:1;background:transparent;font-size:12px" placeholder="搜索 Agent...">
      </div>
      <button class="btn-secondary">导入</button>
    </div>
  </div>

  <div class="agent-grid">
    <AgentCard
      v-for="agent in agentStore.filteredAgents"
      :key="agent.id"
      :agent="agent"
      @use="onUse"
    />

    <!-- Create empty card -->
    <div class="agent-card-empty" @click="emit('create')">
      <div style="width:48px;height:48px;border-radius:50%;background:var(--surface);border:1px solid var(--line);display:grid;place-items:center;color:var(--primary)">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <path d="M5 12h14"/><path d="M12 5v14"/>
        </svg>
      </div>
      <div style="font-size:13px;font-weight:700;color:var(--ink)">自建一个企业 Agent</div>
      <div style="font-size:11.5px;color:var(--ink3);max-width:220px;line-height:1.5">选择基础模型 + 组合技能 + 接入企业知识库</div>
    </div>
  </div>
</template>

<style scoped>
.agent-grid {
  display: grid; grid-template-columns: repeat(3,1fr); gap: 14px;
  flex: 1; overflow-y: auto; padding: 4px; align-content: start;
}
</style>
