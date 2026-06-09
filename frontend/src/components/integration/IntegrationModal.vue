<script setup>
import BaseModal from '@/components/common/BaseModal.vue'
import { useToast } from '@/composables/useToast'

defineProps({ show: Boolean })
const emit = defineEmits(['close'])
const { toast } = useToast()

const SOURCE_TYPES = [
  { icon: '🏛️', bg: 'var(--info-light)', color: 'var(--info)', name: '政府开放平台', desc: '生态环境部、统计局、海关、各省监管平台' },
  { icon: '🏢', bg: '#FEF3C7', color: 'var(--warn)', name: '企业内部系统', desc: 'SAP / 用友 / 金蝶 / MES / 钉钉' },
  { icon: '🔌', bg: 'var(--purple-light)', color: 'var(--purple)', name: 'REST / GraphQL API', desc: '通用 HTTP 接口，支持 OAuth、API Key' },
  { icon: '🗄️', bg: 'var(--primary-light)', color: 'var(--primary)', name: '数据库直连', desc: 'MySQL / PostgreSQL / MongoDB' }
]

function onNext() {
  emit('close')
  toast('已进入下一步：配置认证（演示）', 'info')
}
</script>

<template>
  <BaseModal :show="show" :large="true" @close="emit('close')">
    <template #title>
      <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--primary)">
        <circle cx="12" cy="12" r="10"/><path d="M2 12h20"/>
      </svg>
      新增数据源
    </template>

    <div style="font-size:13px;color:var(--ink2);margin-bottom:14px">选择您要接入的数据源类型：</div>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px">
      <div
        v-for="t in SOURCE_TYPES"
        :key="t.name"
        class="agent-card"
        style="cursor:pointer"
      >
        <div class="agent-card-hdr">
          <div class="agent-ic" :style="{ background: t.bg, color: t.color }">{{ t.icon }}</div>
          <div class="agent-info">
            <div class="agent-name">{{ t.name }}</div>
            <div class="agent-desc">{{ t.desc }}</div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <button class="btn-secondary" @click="emit('close')">取消</button>
      <button class="btn-primary sm" @click="onNext">下一步：配置认证</button>
    </template>
  </BaseModal>
</template>
