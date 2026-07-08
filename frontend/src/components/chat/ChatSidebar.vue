<script setup>
import { onMounted } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useToast } from '@/composables/useToast'

const chat = useChatStore()
const { toast } = useToast()

onMounted(() => {
  chat.loadTasks()
})

async function onTaskClick(task) {
  await chat.setActiveTask(task.id)
  toast(`已切换到任务：${task.title}`, 'info')
}

async function onNewTask() {
  const task = await chat.createTask('新对话')
  toast('已创建新任务', 'ok')
  return task
}

function onSwitchAgent(event) {
  const id = Number(event.target.value)
  const agent = chat.availableAgents.find(a => a.id === id)
  if (agent) {
    chat.setCurrentAgent(agent)
    toast(`已切换到 Agent：${agent.name}`, 'info')
  }
}

async function onTogglePin(task, event) {
  event.stopPropagation()
  const updated = await chat.togglePinTask(task.id)
  toast(updated.pinned ? '已置顶' : '已取消置顶', 'info')
}

async function onDeleteTask(task, event) {
  event.stopPropagation()
  if (!confirm(`确定删除任务「${task.title}」吗？`)) return
  await chat.deleteTask(task.id)
  toast('已删除任务', 'info')
}

const pinnedTasks = () => chat.taskHistory.filter(t => t.pinned)
const recentTasks = () => chat.taskHistory.filter(t => !t.pinned)
</script>

<template>
  <aside class="left-sidebar">
    <div class="left-scroll">
      <!-- New task -->
      <button class="btn-primary" @click="onNewTask">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <path d="M5 12h14"/><path d="M12 5v14"/>
        </svg>
        新建任务
      </button>

      <!-- Current Agent -->
      <div class="card">
        <div class="card-hdr">
          <div class="card-accent"></div>
          <span class="card-title">当前 Agent</span>
          <span class="card-badge">已选</span>
        </div>
        <div class="card-body" style="padding:14px">
          <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px">
            <div class="agent-ic" :style="{ background: chat.currentAgent.bg, color: chat.currentAgent.color, width: '40px', height: '40px' }">
              {{ chat.currentAgent.icon }}
            </div>
            <div style="flex:1">
              <div style="font-size:13px;font-weight:700">{{ chat.currentAgent.name }}</div>
              <div style="font-size:11px;color:var(--ink3)">
                自带 {{ chat.currentAgent.skillCount }} 个技能
                · {{ chat.currentAgent.agentType === 'composite' ? '复合 Agent' : (chat.currentAgent.retrievalMode || 'basic_rag') }}
              </div>
            </div>
          </div>
          <select
            class="btn-secondary"
            style="width:100%; appearance:auto; padding:0 10px"
            @change="onSwitchAgent($event)"
          >
            <option
              v-for="a in chat.availableAgents"
              :key="a.id"
              :value="a.id"
              :selected="a.id === chat.currentAgent.id"
            >
              {{ a.name }}
            </option>
          </select>
        </div>
      </div>

      <!-- Data sources -->
      <div class="card">
        <div class="card-hdr">
          <div class="card-accent card-accent--blue"></div>
          <span class="card-title">数据源</span>
          <span class="card-badge gray">{{ chat.dataSources.length }} 个</span>
        </div>
        <div class="radio-list">
          <div
            v-for="ds in chat.dataSources"
            :key="ds.id"
            class="radio-item"
            @click="chat.toggleDataSource(ds.id)"
          >
            <div class="radio-circle" :class="{ checked: ds.checked }"></div>
            <span class="radio-name">{{ ds.name }}</span>
            <span class="radio-meta">{{ ds.count }}</span>
          </div>
        </div>
      </div>

      <!-- Task history -->
      <div class="card" style="flex:1;display:flex;flex-direction:column;min-height:0">
        <div class="card-hdr">
          <div class="card-accent card-accent--purple"></div>
          <span class="card-title">任务历史</span>
          <button class="icon-btn" style="width:24px;height:24px" @click="chat.loadTasks">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
              <path d="M21 4v8h-8"/>
            </svg>
          </button>
        </div>
        <div style="flex:1;overflow-y:auto;padding:8px 10px">
          <div v-if="chat.loadingTasks" class="hist-group-label">加载中…</div>

          <div class="hist-group-label">置顶</div>
          <div
            v-for="t in pinnedTasks()"
            :key="t.id"
            class="hist-item"
            :class="{ active: t.active }"
            @click="onTaskClick(t)"
          >
            <span class="hist-pin" :class="t.pin"></span>
            <div class="hist-info">
              <div class="hist-q">{{ t.title }}</div>
              <div class="hist-meta">{{ t.meta }}</div>
            </div>
            <div class="hist-actions">
              <button class="icon-btn" @click="onTogglePin(t, $event)">📌</button>
              <button class="icon-btn" @click="onDeleteTask(t, $event)">🗑</button>
            </div>
          </div>

          <div class="hist-group-label">最近</div>
          <div
            v-for="t in recentTasks()"
            :key="t.id"
            class="hist-item"
            :class="{ active: t.active }"
            @click="onTaskClick(t)"
          >
            <span class="hist-pin" :class="t.pin"></span>
            <div class="hist-info">
              <div class="hist-q">{{ t.title }}</div>
              <div class="hist-meta">{{ t.meta }}</div>
            </div>
            <div class="hist-actions">
              <button class="icon-btn" @click="onTogglePin(t, $event)">📌</button>
              <button class="icon-btn" @click="onDeleteTask(t, $event)">🗑</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.hist-actions {
  display: none;
  gap: 4px;
  margin-left: auto;
}
.hist-item:hover .hist-actions {
  display: flex;
}
</style>
