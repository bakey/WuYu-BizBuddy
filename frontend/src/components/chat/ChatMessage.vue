<script setup>
import { useToast } from '@/composables/useToast'
const { toast } = useToast()

defineProps({
  message: { type: Object, required: true }
})

function onAction(label) {
  toast(`操作：${label}`, 'info')
}
</script>

<template>
  <!-- AI message -->
  <div v-if="message.role === 'ai'" class="msg-ai">
    <div class="msg-meta">
      <div class="msg-avatar">AI</div>
      <span class="msg-sender">{{ message.sender }}</span>
      <span class="msg-time">{{ message.time }}</span>
    </div>

    <!-- Thinking state -->
    <div v-if="message.thinking" class="msg-bubble-ai" style="background:var(--info-light);border-color:#DBEAFE">
      <div class="think-status" style="background:transparent;border:0;padding:0">
        <div class="think-dots"><span></span><span></span><span></span></div>
        {{ message.thinking }}
      </div>
    </div>

    <!-- Normal response -->
    <div v-else class="msg-bubble-ai">
      <div v-if="message.skillCall" class="skill-call">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
        </svg>
        {{ message.skillCall }}
      </div>
      <div v-html="message.content"></div>
      <div v-if="message.citations?.length" class="citations">
        <div
          v-for="c in message.citations"
          :key="c.num"
          class="cite"
          @click="toast(`查看引用 ${c.num}`, 'info')"
        >
          <span class="cite-num">{{ c.num }}</span>{{ c.label }}
        </div>
      </div>
      <div v-if="message.actions?.length" class="msg-actions">
        <button
          v-for="a in message.actions"
          :key="a.label"
          class="msg-act-btn"
          :class="{ green: a.variant === 'green' }"
          @click="onAction(a.label)"
        >{{ a.label }}</button>
      </div>
    </div>
  </div>

  <!-- User message -->
  <div v-else class="msg-user">
    <div class="msg-bubble-user">{{ message.content }}</div>
    <span class="msg-user-time">{{ message.time }}</span>
  </div>
</template>

<style scoped>
.msg-ai { display: flex; flex-direction: column; gap: 8px; max-width: 760px; }
.msg-meta { display: flex; align-items: center; gap: 6px; }
.msg-avatar {
  width: 24px; height: 24px; border-radius: 50%;
  background: linear-gradient(135deg,#10B981,#059669); color: #fff;
  font-size: 9px; font-weight: 700; display: grid; place-items: center; flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(5,150,105,.3);
}
.msg-sender { font-size: 11px; font-weight: 600; color: var(--ink2); }
.msg-time   { font-size: 10px; color: var(--ink4); }
.msg-bubble-ai {
  background: var(--surface2); border: 1px solid var(--line);
  border-radius: 0 12px 12px 12px; padding: 14px 16px;
  color: var(--ink2); font-size: 13px; line-height: 1.7;
}
.msg-user { display: flex; flex-direction: column; gap: 4px; align-self: flex-end; max-width: 540px; }
.msg-bubble-user {
  background: linear-gradient(135deg,#10B981,#059669); border-radius: 12px 0 12px 12px;
  padding: 12px 16px; color: #fff; font-size: 13px; line-height: 1.55;
  box-shadow: 0 3px 8px rgba(5,150,105,.2);
}
.msg-user-time { font-size: 10px; color: var(--ink4); align-self: flex-end; }
</style>
