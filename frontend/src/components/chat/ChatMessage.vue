<script setup>
import { useToast } from '@/composables/useToast'
import { useCitationPreview } from '@/composables/useCitationPreview'
import { useChatInput } from '@/composables/useChatInput'
import { downloadText, stripHtml, copyText } from '@/utils/file'
import { computed } from 'vue'

const { toast } = useToast()
const { openPreview } = useCitationPreview()
const { focusInput } = useChatInput()

const props = defineProps({
  message: { type: Object, required: true }
})

const totalElapsed = computed(() => {
  const steps = props.message.trace?.steps || []
  return steps.reduce((sum, s) => sum + (s.elapsed_ms || 0), 0)
})

function statusLabel(status) {
  const map = {
    pending: '待执行',
    running: '执行中',
    completed: '已完成',
    failed: '失败'
  }
  return map[status] || status
}

function scopeLabel(scope) {
  const map = {
    national: '国家级',
    local: '地方级',
    standard: '标准规范',
    case: '案例'
  }
  return map[scope] || scope
}

function roleLabel(role, action) {
  if (role === 'reviewer' || action === 'review') return '评审'
  if (role === 'orchestrator' && action === 'revise') return '修订'
  return ''
}

function onCite(c) {
  if (c.content) openPreview(c)
  else toast('该引用暂无可预览内容', 'warn')
}

async function onAction(label) {
  const text = stripHtml(props.message.content || '')
  if (label === '复制') {
    const ok = await copyText(text)
    toast(ok ? '已复制到剪贴板' : '复制失败', ok ? 'ok' : 'err')
  } else if (label === '导出') {
    const stamp = (props.message.time || '').replace(':', '') || 'export'
    downloadText(`回答-${stamp}.md`, text, 'text/markdown')
    toast('已导出回答（.md）', 'ok')
  } else if (label === '追问') {
    focusInput()
    toast('请在下方输入追问内容', 'info')
  } else {
    toast(`操作：${label}`, 'info')
  }
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

    <!-- Thinking state: 只在还没有回答内容时显示；已经开始输出后就不再顶替内容气泡 -->
    <div v-if="message.thinking && !message.content" class="msg-bubble-ai" style="background:var(--info-light);border-color:#DBEAFE">
      <div class="think-status" style="background:transparent;border:0;padding:0">
        <div class="think-dots"><span></span><span></span><span></span></div>
        {{ message.thinking }}
      </div>
    </div>

    <!-- 意图为 chitchat 时，用一个轻量徽标替代 trace 面板；无需展示 plan/steps/reviews -->
    <div v-if="message.trace && message.trace.intent === 'chitchat'" class="intent-badge">
      <span class="intent-dot"></span>
      识别为寒暄/元问题，跳过检索直接回答
    </div>

    <!-- Execution trace: 常规业务问题才展示完整轨迹面板 -->
    <div v-else-if="message.trace" class="execution-trace">
      <div class="trace-toggle" @click="message._showTrace = !message._showTrace">
        <span class="trace-dot"></span>
        {{ message._showTrace ? '收起执行轨迹' : '查看执行轨迹' }}
        <span class="trace-count">
          {{ message.trace.steps.length }} 步骤
          <span v-if="message.trace.reviews.length">· {{ message.trace.reviews.length }} 评审</span>
        </span>
      </div>
      <div v-if="message._showTrace" class="trace-body">
        <div v-if="message.trace.plan" class="trace-section">
          <div class="trace-title">📋 执行计划</div>
          <div class="trace-text">{{ message.trace.plan.reasoning }}</div>
        </div>
        <div v-if="message.trace.steps.length" class="trace-section">
          <div class="trace-title">🛠️ 执行步骤</div>
          <div class="trace-summary-line">
            共 {{ message.trace.steps.length }} 步 · 总耗时 {{ totalElapsed }} ms
          </div>
          <div
            v-for="step in message.trace.steps"
            :key="step.key || step.step_number"
            class="trace-step"
            :class="{ failed: step.status === 'failed', running: step.status === 'running', pending: step.status === 'pending' }"
          >
            <span class="trace-step-num">#{{ step.step_number }}</span>
            <span v-if="step.revision" class="trace-step-revision">第 {{ step.revision + 1 }} 轮</span>
            <span class="trace-step-action">{{ step.action }}</span>
            <span v-if="roleLabel(step.role, step.action)" class="trace-step-role">{{ roleLabel(step.role, step.action) }}</span>
            <span v-if="step.input?.policy_scope" class="trace-step-scope">{{ scopeLabel(step.input.policy_scope) }}</span>
            <span class="trace-step-status" :class="step.status">{{ statusLabel(step.status) }}</span>
            <span v-if="step.elapsed_ms != null" class="trace-step-time">⏱ {{ step.elapsed_ms }} ms</span>
            <span v-else-if="step.status === 'running'" class="trace-step-time running">执行中…</span>
            <span v-else-if="step.status === 'pending'" class="trace-step-time pending">待执行</span>
            <div v-if="step.reason" class="trace-text">{{ step.reason }}</div>
            <div v-if="step.summary" class="trace-text trace-summary">{{ step.summary }}</div>
            <div v-if="step.error" class="trace-error">{{ step.error }}</div>
          </div>
        </div>
        <div v-if="message.trace.reviews.length" class="trace-section">
          <div class="trace-title">🔍 评审意见</div>
          <div
            v-for="(review, idx) in message.trace.reviews"
            :key="idx"
            class="trace-review"
            :class="{ pass: review.verdict === 'pass', revise: review.verdict === 'revise' }"
          >
            <span class="trace-verdict">{{ review.verdict }}</span>
            <div class="trace-text">{{ review.feedback }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Answer content: 只要有内容就展示，不再依赖 trace/thinking 的 v-else -->
    <div v-if="message.content" class="msg-bubble-ai">
      <div v-if="message.skillCall" class="skill-call">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
        </svg>
        {{ message.skillCall }}
      </div>
      <div v-if="message.phaseStatus" class="phase-status">
        <span class="phase-spinner"></span>
        {{ message.phaseStatus }}
      </div>
      <div v-html="message.content"></div>
      <div v-if="message.citations?.length" class="citations">
        <div
          v-for="c in message.citations"
          :key="c.num"
          class="cite"
          :title="c.content ? '点击预览引用原文' : ''"
          @click="onCite(c)"
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

.execution-trace {
  margin-top: 12px;
  border: 1px dashed var(--line);
  border-radius: 8px;
  background: var(--surface);
  overflow: hidden;
}
.trace-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--ink2);
  cursor: pointer;
  user-select: none;
}
.trace-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #1890FF;
}
.trace-count {
  margin-left: auto;
  color: var(--ink4);
  font-size: 11px;
}
.trace-body {
  padding: 0 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.trace-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.trace-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--ink);
}
.trace-text {
  font-size: 11px;
  color: var(--ink3);
  line-height: 1.5;
}
.trace-step {
  padding: 8px;
  border-radius: 6px;
  background: var(--surface2);
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.trace-step.failed {
  background: #FFF1F0;
  border: 1px solid #FFCCC7;
}
.trace-step-num {
  font-size: 10px;
  color: var(--ink4);
}
.trace-step-action {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink2);
}
.trace-step-scope {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  background: #F0F5FF;
  color: #2F54EB;
}
.trace-step-role {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  background: #FFF7E6;
  color: #FA8C16;
}
.trace-step-revision {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  background: #FFF0F6;
  color: #EB2F96;
}
.intent-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 12px; margin-top: 4px;
  font-size: 11px; color: #722ED1;
  background: #F9F0FF; border: 1px solid #EFDBFF; border-radius: 12px;
  align-self: flex-start;
}
.intent-dot {
  width: 6px; height: 6px; border-radius: 50%; background: #722ED1;
}
.phase-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: #1890FF;
  background: #E6F7FF;
  border: 1px solid #91D5FF;
  border-radius: 12px;
  padding: 3px 10px;
  margin-bottom: 8px;
}
.phase-spinner {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #1890FF;
  animation: pulse 1.2s ease-in-out infinite;
}
.trace-step-status {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  background: #E6F7FF;
  color: #1890FF;
}
.trace-step.pending {
  opacity: 0.7;
  background: var(--surface2);
}
.trace-step.running {
  background: #FFFBE6;
  border: 1px solid #FFD591;
  box-shadow: 0 0 0 2px rgba(250, 140, 22, 0.15);
}
.trace-step-status.pending {
  background: #F5F5F5;
  color: var(--ink4);
}
.trace-step-status.running {
  background: #FFF7E6;
  color: #FA8C16;
  animation: pulse 1.5s infinite;
}
.trace-step-status.completed {
  background: #F6FFED;
  color: #52C41A;
}
.trace-step-status.failed {
  background: #FFF1F0;
  color: #CF1322;
}
.trace-step-time {
  margin-left: auto;
  font-size: 10px;
  color: var(--ink4);
  font-family: monospace;
}
.trace-step-time.running {
  color: #FA8C16;
}
.trace-step-time.pending {
  color: var(--ink4);
}
@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.6; }
  100% { opacity: 1; }
}
.trace-summary-line {
  font-size: 11px;
  color: var(--ink3);
  margin-bottom: 6px;
}
.trace-summary {
  width: 100%;
  margin-top: 4px;
}
.trace-error {
  width: 100%;
  color: #CF1322;
  font-size: 11px;
}
.trace-review {
  padding: 8px;
  border-radius: 6px;
  background: var(--surface2);
}
.trace-review.pass {
  background: #F6FFED;
  border: 1px solid #B7EB8F;
}
.trace-review.revise {
  background: #FFF7E6;
  border: 1px solid #FFD591;
}
.trace-verdict {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}
</style>
