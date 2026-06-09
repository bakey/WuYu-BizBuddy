<script setup>
import { useDatabaseStore } from '@/stores/database'
import { useToast }         from '@/composables/useToast'

const store  = useDatabaseStore()
const { toast } = useToast()

function onView(db)    { toast('已打开详情', 'info') }
function onClean(db)   { toast('已触发清洗任务', 'info') }
function onRefresh(db) { toast('已重新同步', 'ok') }
</script>

<template>
  <div class="card db-table">
    <div class="card-hdr">
      <div class="card-accent"></div>
      <span class="card-title">数据库列表 · {{ store.databases.length }} 个核心库</span>
      <button class="btn-secondary" style="height:28px" @click="toast('请配置新库参数', 'info')">+ 新建库</button>
    </div>

    <!-- Header -->
    <div class="db-row head">
      <div></div><div>库名</div><div>记录数</div><div>大小</div><div>索引状态</div><div>健康</div><div>操作</div>
    </div>

    <!-- Data rows -->
    <div
      v-for="db in store.databases"
      :key="db.id"
      class="db-row"
      :style="{ opacity: db.disabled ? 0.55 : 1 }"
    >
      <div class="db-ic" :style="{ background: db.iconBg, color: db.iconColor, fontSize: '16px' }">{{ db.icon }}</div>
      <div class="db-name">
        <div class="nm">{{ db.name }}</div>
        <div class="meta">{{ db.meta }}</div>
      </div>
      <div class="db-num">{{ db.records }}</div>
      <div class="db-num">{{ db.size }}</div>
      <div><span class="st" :class="db.indexStatus">{{ db.indexLabel }}</span></div>
      <div class="health-bar" v-if="!db.disabled">
        <div class="health-track">
          <div class="health-fill" :class="db.healthCls" :style="{ width: db.health + '%' }"></div>
        </div>
      </div>
      <div v-else class="health-bar"><div class="health-track"></div></div>
      <div class="row-actions">
        <button class="row-act" @click="onView(db)" title="查看">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>
          </svg>
        </button>
        <button v-if="!db.disabled" class="row-act" @click="onClean(db)" title="清洗">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6 5 4l4 4 4-4 4 4 2-2"/><path d="m3 18 2 2 4-4 4 4 4-4 2 2"/>
          </svg>
        </button>
        <button v-if="!db.disabled" class="row-act" @click="onRefresh(db)" title="同步">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
          </svg>
        </button>
        <button v-else class="row-act" @click="toast('启用 remote_sensing_db', 'info')" title="启用">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M5 12h14"/><path d="M12 5v14"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.db-table .db-row {
  display: grid;
  grid-template-columns: 32px minmax(220px,1fr) 110px 90px 130px 110px 100px;
  gap: 14px; align-items: center;
  padding: 12px 18px; border-bottom: 1px solid var(--line); transition: background .1s;
}
.db-table .db-row:last-child { border-bottom: none; }
.db-table .db-row:hover { background: var(--surface2); }
.db-table .db-row.head { background: var(--surface2); font-size: 11px; font-weight: 600; color: var(--ink4); letter-spacing: .2px; padding: 10px 18px; text-transform: uppercase; }
.db-ic   { width: 32px; height: 32px; border-radius: 8px; display: grid; place-items: center; }
.db-name .nm   { font-size: 13px; font-weight: 600; color: var(--ink); }
.db-name .meta { font-size: 11px; color: var(--ink3); margin-top: 2px; }
.db-num  { font-size: 12.5px; color: var(--ink2); font-variant-numeric: tabular-nums; font-weight: 500; }
</style>
