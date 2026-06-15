<script setup>
defineProps({
  agent: { type: Object, required: true }
})
const emit = defineEmits(['use'])
</script>

<template>
  <div class="agent-card" :class="{ featured: agent.featured }">
    <div class="agent-card-hdr">
      <div class="agent-ic" :style="{ background: agent.bg, color: agent.color }">
        {{ agent.icon }}
      </div>
      <div class="agent-info">
        <div class="agent-name-row">
          <span class="agent-name">{{ agent.name }}</span>
          <span v-if="agent.tag" class="tag" :class="agent.tag.cls">{{ agent.tag.label }}</span>
        </div>
        <div class="agent-desc">{{ agent.desc }}</div>
      </div>
    </div>

    <div class="agent-skills-area">
      <div class="agent-skills-label">⚡ 自带技能 · {{ agent.skills.length }}</div>
      <div class="agent-skill-chips">
        <span v-for="s in agent.skills" :key="s" class="agent-skill-chip">{{ s }}</span>
        <span class="agent-skill-chip add">+ 添加</span>
      </div>
    </div>

    <div class="agent-foot">
      <div class="agent-meta">
        <span>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
          </svg>{{ agent.users }}
        </span>
        <span>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="#F59E0B">
            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
          </svg>{{ agent.rating }}
        </span>
      </div>
      <button
        class="btn-primary sm"
        v-if="agent.featured"
        @click.stop="emit('use', agent)"
      >立即使用 →</button>
      <button
        class="btn-secondary"
        v-else
        @click.stop="emit('use', agent)"
      >立即使用</button>
    </div>
  </div>
</template>
