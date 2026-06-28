<script setup>
import { useKnowledgeStore } from '@/stores/knowledge'

const store = useKnowledgeStore()

// /retrieve 返回的 score 是 pgvector 余弦相似度（原始值），原样按 4 位展示，排序意义看顺序
function fmtScore(s) {
  const n = Number(s)
  return Number.isFinite(n) ? n.toFixed(4) : '—'
}
</script>

<template>
  <div class="card">
    <div class="card-hdr">
      <div class="card-accent card-accent--blue"></div>
      <span class="card-title">检索测试</span>
      <span class="card-badge gray">向量检索 · 不调 LLM</span>
    </div>

    <div class="rt-body">
      <div class="rt-search">
        <input
          v-model="store.retrieveQuery"
          class="form-input"
          type="text"
          placeholder="输入问题，对已索引文档做向量检索（如：江苏对无废园区的资金支持力度）"
          @keyup.enter="store.runRetrieve()"
        />
        <select v-model.number="store.retrieveTopK" class="form-input rt-topk" title="返回条数">
          <option :value="3">Top 3</option>
          <option :value="5">Top 5</option>
          <option :value="10">Top 10</option>
        </select>
        <button class="btn-primary sm" :disabled="store.retrieveLoading" @click="store.runRetrieve()">
          {{ store.retrieveLoading ? '检索中…' : '检索' }}
        </button>
      </div>

      <!-- loading -->
      <div v-if="store.retrieveLoading" class="think-status rt-mt">
        <span>正在向量检索</span>
        <span class="think-dots"><span></span><span></span><span></span></span>
      </div>

      <!-- error -->
      <div v-else-if="store.retrieveError" class="rt-hint">
        <span class="st err"><span class="st-dot"></span>检索失败</span>
        <span class="rt-muted">{{ store.retrieveError }}（确认后端 :8000 在运行）</span>
      </div>

      <!-- results -->
      <div v-else-if="store.retrieveResults.length" class="rt-list">
        <div v-for="(r, i) in store.retrieveResults" :key="i" class="rt-item">
          <div class="rt-rank">{{ i + 1 }}</div>
          <div class="rt-main">
            <div class="rt-meta">
              <span class="pill" :title="'cosine 相似度 ' + fmtScore(r.score)">{{ fmtScore(r.score) }}</span>
              <span class="rt-src">{{ r.source || '未知来源' }}</span>
              <span v-if="r.metadata && r.metadata.region" class="tag tag-blue">{{ r.metadata.region }}</span>
            </div>
            <div class="rt-content">{{ r.content }}</div>
          </div>
        </div>
      </div>

      <!-- empty after search -->
      <div v-else-if="store.retrieveDone" class="rt-hint">
        <span class="rt-muted">未检索到相关内容。换个说法，或先在上方上传文档。</span>
      </div>

      <!-- idle -->
      <div v-else class="rt-hint">
        <span class="rt-muted">对知识库已索引文档做纯向量检索预览，按相似度（cosine）排序，不消耗 LLM。</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.rt-body { padding: 14px 18px; }
.rt-search { display: flex; gap: 8px; align-items: center; }
.rt-search .form-input { flex: 1; }
.rt-topk { flex: 0 0 92px; width: 92px; cursor: pointer; }
.rt-search .btn-primary.sm { flex-shrink: 0; }
.rt-mt { margin-top: 12px; }
.rt-hint { margin-top: 12px; font-size: 12px; display: flex; align-items: center; gap: 8px; }
.rt-muted { color: var(--ink3); }
.rt-list { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.rt-item { display: flex; gap: 12px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface2); }
.rt-rank { width: 22px; height: 22px; flex-shrink: 0; border-radius: 6px; background: var(--primary); color: #fff; font-size: 12px; font-weight: 700; display: grid; place-items: center; }
.rt-main { flex: 1; min-width: 0; }
.rt-meta { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.rt-src { font-size: 12px; font-weight: 600; color: var(--ink2); }
.rt-content { font-size: 12.5px; color: var(--ink); line-height: 1.6; word-break: break-word; }
</style>
