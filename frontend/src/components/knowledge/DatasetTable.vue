<script setup>
import { useKnowledgeStore } from '@/stores/knowledge'
import { useToast }          from '@/composables/useToast'

const store  = useKnowledgeStore()
const { toast } = useToast()

function onView(ds)    { toast('已打开详情', 'info') }
function onRefresh(ds) { toast('已重新同步', 'ok')   }
async function onDelete(ds)  {
  if (!confirm('确定删除该数据集？')) return
  const ok = await store.removeDataset(ds.id)
  toast(ok ? '已删除' : '删除失败，请重试', ok ? 'ok' : 'err')
}
function onPause(ds)  { toast('已暂停', 'warn') }
async function onCancel(ds) {
  await store.removeDataset(ds.id)
  toast('已取消上传', 'warn')
}
</script>

<template>
  <div class="card">
    <div class="card-hdr">
      <div class="card-accent"></div>
      <span class="card-title">已上传的数据集</span>
      <span class="card-badge gray">{{ store.datasets.length }}</span>
    </div>

    <!-- Header row -->
    <div class="ds-row" style="background:var(--surface2);font-size:11px;font-weight:600;color:var(--ink4);text-transform:uppercase;padding:10px 18px">
      <div></div><div>数据集</div><div>状态</div><div>关联库</div><div>操作</div>
    </div>

    <!-- Data rows -->
    <div v-for="ds in store.datasets" :key="ds.id" class="ds-row">
      <div class="ds-ic" :style="{ background: ds.iconBg, color: ds.iconColor, fontSize: '20px' }">{{ ds.icon }}</div>
      <div>
        <div class="ds-name">{{ ds.name }}</div>
        <div class="ds-meta">
          <span>{{ ds.count }}</span>
          <span>{{ ds.size }}</span>
          <span>{{ ds.date }}</span>
        </div>
        <div v-if="ds.progress !== null && ds.status === 'warn'" class="progress-bar">
          <div class="progress-fill" :style="{ width: ds.progress + '%' }"></div>
        </div>
      </div>
      <div>
        <span class="st" :class="ds.status"><span class="st-dot"></span>{{ ds.statusLabel }}</span>
      </div>
      <div style="font-size:11.5px">
        <span v-if="ds.linkedDb" class="tag" :class="ds.linkedTag">{{ ds.linkedDb }}</span>
        <span v-else style="color:var(--ink4)">独立索引</span>
      </div>
      <div class="row-actions">
        <!-- Uploading state -->
        <template v-if="ds.status === 'warn' && ds.progress !== null">
          <button class="row-act" @click="onPause(ds)" title="暂停">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>
            </svg>
          </button>
          <button class="row-act" @click="onCancel(ds)" title="取消">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </template>

        <!-- Ready state -->
        <template v-else>
          <button class="row-act" @click="onView(ds)" title="查看">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>
            </svg>
          </button>
          <button class="row-act" @click="onRefresh(ds)" title="同步">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
            </svg>
          </button>
          <button class="row-act" style="color:var(--danger)" @click="onDelete(ds)" title="删除">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
              <path d="M10 11v6"/><path d="M14 11v6"/>
            </svg>
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ds-row {
  display: grid;
  grid-template-columns: 40px minmax(260px,1fr) 110px 140px 110px;
  gap: 14px; align-items: center;
  padding: 14px 18px; border-bottom: 1px solid var(--line);
}
.ds-row:last-child { border-bottom: none; }
.ds-ic   { width: 40px; height: 40px; border-radius: 8px; display: grid; place-items: center; }
.ds-name { font-size: 13px; font-weight: 600; color: var(--ink); }
.ds-meta { font-size: 11.5px; color: var(--ink3); margin-top: 3px; display: flex; gap: 12px; }
</style>
