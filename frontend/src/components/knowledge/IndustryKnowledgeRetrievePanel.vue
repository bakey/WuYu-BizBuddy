<script setup>
import { useIndustryKnowledgeStore } from '@/stores/industryKnowledge'

const store = useIndustryKnowledgeStore()

// fulltext 模式 score 是 ts_rank（小数值），原样按 4 位展示，仅表示相对排序意义
function fmtScore(s) {
  const n = Number(s)
  return Number.isFinite(n) ? n.toFixed(4) : '—'
}
</script>

<template>
  <div class="card">
    <div class="card-hdr">
      <div class="card-accent card-accent--purple"></div>
      <span class="card-title">行业知识检索测试</span>
      <span class="card-badge gray">skill · 纯检索 · 不调 LLM</span>
    </div>

    <div class="ikr-body">
      <!-- 与下方「行业知识问答」共享同一个 store.ikSkillId，填一次两边同步 -->
      <div class="ikr-skill">
        <label class="ikr-skill-label">Skill ID</label>
        <input
          v-model="store.ikSkillId"
          class="form-input"
          type="text"
          placeholder="行业知识 skill 的 UUID"
        />
      </div>

      <div class="ikr-search">
        <input
          v-model="store.ikRetrieveQuery"
          class="form-input"
          type="text"
          placeholder="对该 skill 做纯检索预览（演示数据可试：无废园区 / 危废 / 专项资金）"
          @keyup.enter="store.runIkRetrieve()"
        />
        <select v-model.number="store.ikRetrieveTopK" class="form-input ikr-topk" title="检索条数">
          <option :value="3">Top 3</option>
          <option :value="5">Top 5</option>
          <option :value="10">Top 10</option>
        </select>
        <button class="btn-primary sm" :disabled="store.ikRetrieveLoading" @click="store.runIkRetrieve()">
          {{ store.ikRetrieveLoading ? '检索中…' : '检索' }}
        </button>
      </div>

      <!-- loading -->
      <div v-if="store.ikRetrieveLoading" class="think-status ikr-mt">
        <span>正在检索行业知识</span>
        <span class="think-dots"><span></span><span></span><span></span></span>
      </div>

      <!-- error -->
      <div v-else-if="store.ikRetrieveError" class="ikr-hint">
        <span class="st err"><span class="st-dot"></span>检索失败</span>
        <span class="ikr-muted">{{ store.ikRetrieveError }}</span>
      </div>

      <!-- results -->
      <div v-else-if="store.ikRetrieveResults.length" class="ikr-list">
        <div v-for="(r, i) in store.ikRetrieveResults" :key="(r.segment_id || 'seg') + '-' + i" class="ikr-item">
          <div class="ikr-rank">{{ i + 1 }}</div>
          <div class="ikr-main">
            <div class="ikr-meta">
              <span class="pill" :title="'相关度 ' + fmtScore(r.score)">{{ fmtScore(r.score) }}</span>
              <span class="ikr-src">{{ (r.metadata && r.metadata.title) || r.source || '未知来源' }}</span>
              <span v-if="r.metadata && r.metadata.region" class="tag tag-blue">{{ r.metadata.region }}</span>
            </div>
            <div class="ikr-content">{{ r.content }}</div>
          </div>
        </div>
      </div>

      <!-- empty after search -->
      <div v-else-if="store.ikRetrieveDone" class="ikr-hint">
        <span class="ikr-muted">未检索到相关依据。换个说法，或确认该 skill 的数据集已建好索引。</span>
      </div>

      <!-- idle -->
      <div v-else class="ikr-hint">
        <span class="ikr-muted">对指定 skill 做纯检索预览，只返回证据片段，不调用 LLM、不计入问答日志。</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ikr-body { padding: 14px 18px; }
.ikr-skill { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.ikr-skill-label { flex: 0 0 auto; font-size: 12px; color: var(--ink3); }
.ikr-skill .form-input { flex: 1; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
.ikr-search { display: flex; gap: 8px; align-items: center; }
.ikr-search .form-input { flex: 1; }
.ikr-topk { flex: 0 0 92px; width: 92px; cursor: pointer; }
.ikr-search .btn-primary.sm { flex-shrink: 0; }
.ikr-mt { margin-top: 12px; }
.ikr-hint { margin-top: 12px; font-size: 12px; display: flex; align-items: center; gap: 8px; }
.ikr-muted { color: var(--ink3); }
.ikr-list { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.ikr-item { display: flex; gap: 12px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface2); }
.ikr-rank { width: 22px; height: 22px; flex-shrink: 0; border-radius: 6px; background: var(--purple); color: #fff; font-size: 12px; font-weight: 700; display: grid; place-items: center; }
.ikr-main { flex: 1; min-width: 0; }
.ikr-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.ikr-src { font-size: 12px; font-weight: 600; color: var(--ink2); }
.ikr-content { font-size: 12.5px; color: var(--ink); line-height: 1.6; word-break: break-word; }
</style>
