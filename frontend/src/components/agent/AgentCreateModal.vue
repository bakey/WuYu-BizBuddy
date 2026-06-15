<script setup>
import { ref } from 'vue'
import BaseModal from '@/components/common/BaseModal.vue'
import { useAgentStore } from '@/stores/agent'
import { useToast }      from '@/composables/useToast'

defineProps({ show: Boolean })
const emit = defineEmits(['close'])

const agentStore = useAgentStore()
const { toast }  = useToast()

const name   = ref('')
const model  = ref('Wuyu-7B')
const desc   = ref('检索企业内部合规文档与最新法规，输出合规自检清单与风险提示。')
const MODELS = ['Wuyu-7B', 'Wuyu-Pro 32B', 'GPT-4o']
const ALL_SKILLS = ['政策检索','条文比对','影响评估','合规清单','企业画像','技术对比','实体检索','交叉验证']
const selectedSkills = ref(['政策检索', '条文比对'])
const linkedSources  = ref(['企业知识库', 'policy_db'])

function toggleSkill(s) {
  const idx = selectedSkills.value.indexOf(s)
  idx > -1 ? selectedSkills.value.splice(idx, 1) : selectedSkills.value.push(s)
}

function handleCreate() {
  const agentName = name.value.trim() || '我的 Agent'
  agentStore.createAgent({
    name: agentName,
    desc: desc.value,
    icon: '🤖',
    bg: 'var(--surface2)',
    color: 'var(--ink2)',
    skills: [...selectedSkills.value],
    category: '企业自建'
  })
  emit('close')
  toast(`Agent 「${agentName}」已创建`, 'ok')
}
</script>

<template>
  <BaseModal :show="show" title="自建一个企业 Agent" @close="emit('close')">
    <template #title>
      <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--primary)">
        <path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/>
        <path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/>
      </svg>
      自建一个企业 Agent
    </template>

    <div class="form-group" style="margin-bottom:14px">
      <label class="form-label">Agent 名称</label>
      <input v-model="name" class="form-input" placeholder="例如：固废合规审查官">
    </div>

    <div class="form-group" style="margin-bottom:14px">
      <label class="form-label">基础模型</label>
      <div class="row" style="gap:8px">
        <button
          v-for="m in MODELS"
          :key="m"
          class="btn-mode"
          :class="{ active: model === m }"
          @click="model = m"
        >{{ m }}</button>
      </div>
    </div>

    <div class="form-group" style="margin-bottom:14px">
      <label class="form-label">技能组合（多选）</label>
      <div class="chips" style="margin-top:4px">
        <div
          v-for="s in ALL_SKILLS"
          :key="s"
          class="chip"
          :class="{ active: selectedSkills.includes(s) }"
          @click="toggleSkill(s)"
        >{{ s }}</div>
      </div>
    </div>

    <div class="form-group" style="margin-bottom:14px">
      <label class="form-label">Agent 描述</label>
      <textarea v-model="desc" class="form-input" rows="3" style="height:auto;padding:10px;font-family:inherit;line-height:1.5"></textarea>
    </div>

    <div class="form-group">
      <label class="form-label">数据源链接</label>
      <div style="display:flex;flex-direction:column;gap:6px;margin-top:4px">
        <label v-for="s in ['企业知识库','policy_db','paper_db']" :key="s" style="display:flex;align-items:center;gap:8px;font-size:12.5px;cursor:pointer">
          <input type="checkbox" :value="s" v-model="linkedSources" style="accent-color:var(--primary)">
          {{ s }}
        </label>
      </div>
    </div>

    <template #footer>
      <button class="btn-secondary" @click="emit('close')">取消</button>
      <button class="btn-primary sm" @click="handleCreate">创建 Agent</button>
    </template>
  </BaseModal>
</template>
