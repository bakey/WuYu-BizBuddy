<script setup>
import { useIndustryKnowledgeStore } from '@/stores/industryKnowledge'
import { useToast } from '@/composables/useToast'

const store = useIndustryKnowledgeStore()
const { toast } = useToast()

// fulltext 模式 score 是 ts_rank（小数值），原样按 4 位展示，仅表示相对排序意义
function fmtScore(s) {
  const n = Number(s)
  return Number.isFinite(n) ? n.toFixed(4) : '—'
}

async function vote(isHelpful) {
  const ok = await store.submitFeedback(isHelpful)
  if (ok) toast('感谢反馈', 'ok')
  else toast('反馈提交失败（确认后端 :8000 在运行）', 'err')
}
</script>

<template>
  <div class="card">
    <div class="card-hdr">
      <div class="card-accent card-accent--purple"></div>
      <span class="card-title">行业知识问答</span>
      <span class="card-badge gray">skill · 检索 + LLM + 反馈</span>
    </div>

    <div class="ik-body">
      <!-- 当前无 skill 列表接口，直接填 skill_id（默认本地演示 skill） -->
      <div class="ik-skill">
        <label class="ik-skill-label">Skill ID</label>
        <input
          v-model="store.ikSkillId"
          class="form-input"
          type="text"
          placeholder="行业知识 skill 的 UUID"
        />
      </div>

      <div class="ik-search">
        <input
          v-model="store.ikQuery"
          class="form-input"
          type="text"
          placeholder="向该 skill 提问（演示数据可试：无废园区 / 危废 / 专项资金）"
          @keyup.enter="store.runQuery()"
        />
        <select v-model.number="store.ikTopK" class="form-input ik-topk" title="检索条数">
          <option :value="3">Top 3</option>
          <option :value="5">Top 5</option>
          <option :value="10">Top 10</option>
        </select>
        <button class="btn-primary sm" :disabled="store.ikLoading" @click="store.runQuery()">
          {{ store.ikLoading ? '生成中…' : '提问' }}
        </button>
      </div>

      <!-- loading -->
      <div v-if="store.ikLoading" class="think-status ik-mt">
        <span>正在检索行业知识并生成回答</span>
        <span class="think-dots"><span></span><span></span><span></span></span>
      </div>

      <!-- error -->
      <div v-else-if="store.ikError" class="ik-hint">
        <span class="st err"><span class="st-dot"></span>问答失败</span>
        <span class="ik-muted">{{ store.ikError }}</span>
      </div>

      <!-- answer + references -->
      <div v-else-if="store.ikDone && (store.ikAnswer || store.ikReferences.length)" class="ik-result">
        <div v-if="store.ikAnswer" class="ik-answer">
          <div class="ik-answer-hd">
            <span class="skill-call">skill 回答</span>
            <!-- 反馈：依赖本次问答的 query_log_id -->
            <div v-if="store.ikQueryLogId" class="ik-fb">
              <button
                class="msg-act-btn"
                :class="{ green: store.ikFeedback === 'up' }"
                :disabled="store.ikFeedbackSubmitting || !!store.ikFeedback"
                :aria-pressed="store.ikFeedback === 'up'"
                title="有帮助"
                @click="vote(true)"
              >
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M7 11v9M2 13v6a1 1 0 0 0 1 1h3V11H3a1 1 0 0 0-1 1zM7 11l4-8a2 2 0 0 1 2 2v4h5a2 2 0 0 1 2 2.3l-1.3 7A2 2 0 0 1 16.7 22H7"/></svg>
                有帮助
              </button>
              <button
                class="msg-act-btn"
                :class="{ 'ik-down-on': store.ikFeedback === 'down' }"
                :disabled="store.ikFeedbackSubmitting || !!store.ikFeedback"
                :aria-pressed="store.ikFeedback === 'down'"
                title="没帮助"
                @click="vote(false)"
              >
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M17 13V4M22 11V5a1 1 0 0 0-1-1h-3v9h3a1 1 0 0 0 1-1zM17 13l-4 8a2 2 0 0 1-2-2v-4H6a2 2 0 0 1-2-2.3l1.3-7A2 2 0 0 1 7.3 2H17"/></svg>
                没帮助
              </button>
            </div>
          </div>
          <div class="ik-answer-body">{{ store.ikAnswer }}</div>
        </div>

        <div v-if="store.ikReferences.length" class="ik-refs">
          <div class="ik-refs-hd">引用依据 · {{ store.ikReferences.length }} 条</div>
          <div class="ik-list">
            <div v-for="(r, i) in store.ikReferences" :key="(r.segment_id || 'seg') + '-' + i" class="ik-item">
              <div class="ik-rank">{{ i + 1 }}</div>
              <div class="ik-main">
                <div class="ik-meta">
                  <span class="pill" :title="'相关度 ' + fmtScore(r.score)">{{ fmtScore(r.score) }}</span>
                  <span class="ik-src">{{ (r.metadata && r.metadata.title) || r.source || '未知来源' }}</span>
                  <span v-if="r.metadata && r.metadata.region" class="tag tag-blue">{{ r.metadata.region }}</span>
                </div>
                <div class="ik-content">{{ r.content }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- empty after query -->
      <div v-else-if="store.ikDone" class="ik-hint">
        <span class="ik-muted">未检索到相关依据。换个说法，或确认该 skill 的数据集已建好索引。</span>
      </div>

      <!-- idle -->
      <div v-else class="ik-hint">
        <span class="ik-muted">面向某个行业知识 skill 做「检索 + LLM 问答」，返回带依据的回答，并可对回答赞/踩反馈。</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ik-body { padding: 14px 18px; }
.ik-skill { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.ik-skill-label { flex: 0 0 auto; font-size: 12px; color: var(--ink3); }
.ik-skill .form-input { flex: 1; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.ik-search { display: flex; gap: 8px; align-items: center; }
.ik-search .form-input { flex: 1; }
.ik-topk { flex: 0 0 92px; width: 92px; cursor: pointer; }
.ik-search .btn-primary.sm { flex-shrink: 0; }
.ik-mt { margin-top: 12px; }
.ik-hint { margin-top: 12px; font-size: 12px; display: flex; align-items: center; gap: 8px; }
.ik-muted { color: var(--ink3); }
.ik-result { margin-top: 12px; display: flex; flex-direction: column; gap: 12px; }
.ik-answer { border: 1px solid var(--primary-border); border-radius: 8px; background: var(--primary-light); padding: 12px 14px; }
.ik-answer-hd { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.ik-fb { display: flex; gap: 6px; }
.ik-fb .ik-down-on,
.ik-fb .ik-down-on:hover { color: var(--danger); border-color: var(--danger); }
.ik-answer-body { font-size: 12.5px; color: var(--ink); line-height: 1.7; white-space: pre-wrap; word-break: break-word; }
.ik-refs-hd { font-size: 12px; color: var(--ink3); margin-bottom: 6px; }
.ik-list { display: flex; flex-direction: column; gap: 8px; }
.ik-item { display: flex; gap: 12px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface2); }
.ik-rank { width: 22px; height: 22px; flex-shrink: 0; border-radius: 6px; background: var(--purple); color: #fff; font-size: 12px; font-weight: 700; display: grid; place-items: center; }
.ik-main { flex: 1; min-width: 0; }
.ik-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.ik-src { font-size: 12px; font-weight: 600; color: var(--ink2); }
.ik-content { font-size: 12.5px; color: var(--ink); line-height: 1.6; word-break: break-word; }
</style>
