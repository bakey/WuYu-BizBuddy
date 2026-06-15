<script setup>
import { useIntegrationStore } from '@/stores/integration'
import { useToast }            from '@/composables/useToast'

const emit  = defineEmits(['add'])
const store = useIntegrationStore()
const { toast } = useToast()

function onView(src)    { toast('已打开详情', 'info') }
function onRefresh(src) { toast('已重新同步', 'ok')   }
function onMore(src)    { toast('更多操作', 'info')    }
function onDelete(src)  {
  if (confirm('确定删除该数据源？')) {
    store.removeSource(src.id)
    toast('已删除', 'ok')
  }
}
</script>

<template>
  <div class="integ-list">
    <div class="integ-list-hdr">
      <h3>已接入数据源 · {{ store.dataSources.length }}</h3>
      <div class="row">
        <input class="form-input" style="width:200px;height:30px;font-size:12px" placeholder="搜索数据源...">
        <button class="btn-secondary">过滤</button>
      </div>
    </div>

    <!-- Header row -->
    <div class="integ-row head">
      <div></div><div>数据源</div><div>状态</div><div>频率</div><div>累计量</div><div>操作</div>
    </div>

    <!-- Data rows -->
    <div v-for="src in store.dataSources" :key="src.id" class="integ-row">
      <div class="integ-src-ic" :style="{ background: src.iconBg, color: src.iconColor, fontSize: '20px' }">{{ src.icon }}</div>
      <div class="integ-src">
        <div class="nm">{{ src.name }}</div>
        <div class="ds">{{ src.desc }}</div>
      </div>
      <div><span class="st" :class="src.status"><span class="st-dot"></span>{{ src.statusLabel }}</span></div>
      <div class="freq">{{ src.freq }}</div>
      <div class="vol">{{ src.volume }}</div>
      <div class="row-actions">
        <button class="row-act" @click="onView(src)" title="查看">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>
          </svg>
        </button>
        <button class="row-act" @click="onRefresh(src)" title="同步">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
          </svg>
        </button>
        <button class="row-act" @click="onMore(src)" title="更多">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.integ-list { background: var(--surface); border-radius: var(--radius); border: 1px solid var(--line); box-shadow: var(--shadow-card); overflow: hidden; }
.integ-list-hdr { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid var(--line); }
.integ-list-hdr h3 { font-size: 14px; font-weight: 700; }
.integ-row {
  display: grid;
  grid-template-columns: 40px minmax(280px,1fr) 130px 100px 130px 100px;
  gap: 14px; align-items: center;
  padding: 12px 18px; border-bottom: 1px solid var(--line); transition: background .1s;
}
.integ-row:last-child { border-bottom: none; }
.integ-row:hover { background: var(--surface2); }
.integ-row.head { background: var(--surface2); font-size: 11px; font-weight: 600; color: var(--ink4); letter-spacing: .2px; padding: 10px 18px; text-transform: uppercase; }
.integ-src-ic { width: 40px; height: 40px; border-radius: 8px; display: grid; place-items: center; }
.integ-src .nm { font-size: 13px; font-weight: 600; color: var(--ink); }
.integ-src .ds { font-size: 11px; color: var(--ink3); margin-top: 2px; }
.freq { font-size: 11.5px; color: var(--ink2); }
.vol  { font-size: 12.5px; color: var(--ink); font-weight: 600; }
</style>
