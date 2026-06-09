<script setup>
import { useKnowledgeStore } from '@/stores/knowledge'
import { useToast }          from '@/composables/useToast'

const store  = useKnowledgeStore()
const { toast } = useToast()

function onUpload() {
  toast('请使用拖拽上传区域上传文件', 'info')
}
</script>

<template>
  <aside class="left-sidebar">
    <div class="left-scroll">
      <button class="btn-primary" @click="onUpload">
        <svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
        上传数据
      </button>

      <!-- Dataset groups -->
      <div class="card">
        <div class="card-hdr">
          <div class="card-accent"></div>
          <span class="card-title">数据集分组</span>
          <span class="card-badge gray">{{ store.groups.reduce((s,g)=>s+g.count,0) }}</span>
        </div>
        <div style="padding:6px 10px">
          <div
            v-for="g in store.groups"
            :key="g.name"
            class="hist-item"
            :class="{ active: g.active }"
            @click="store.setGroup(g.name)"
          >
            <span style="font-size:14px">{{ g.icon }}</span>
            <div class="hist-info">
              <div class="hist-q">{{ g.name }}</div>
              <div class="hist-meta">{{ g.count }} 个{{ g.meta ? ' · ' + g.meta : '' }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Index status -->
      <div class="card">
        <div class="card-hdr"><div class="card-accent card-accent--orange"></div><span class="card-title">索引状态</span></div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:6px">
          <label v-for="s in store.indexStatuses" :key="s.label" style="display:flex;align-items:center;gap:8px;font-size:12px;cursor:pointer">
            <input type="checkbox" v-model="s.checked" style="accent-color:var(--primary)">
            {{ s.label }}
            <span style="color:var(--ink4);margin-left:auto">{{ s.count }}</span>
          </label>
        </div>
      </div>

      <!-- Permission -->
      <div class="card">
        <div class="card-hdr"><div class="card-accent card-accent--blue"></div><span class="card-title">权限设置</span></div>
        <div class="card-body" style="display:flex;flex-direction:column;gap:8px">
          <div style="font-size:12px;color:var(--ink2)">默认可见性</div>
          <div class="row" style="gap:6px">
            <button
              v-for="v in ['仅我','部门','公司']"
              :key="v"
              class="btn-mode"
              :class="{ active: store.visibility === (v === '仅我' ? 'me' : v === '部门' ? 'dept' : 'company') }"
              @click="store.setVisibility(v === '仅我' ? 'me' : v === '部门' ? 'dept' : 'company')"
            >{{ v }}</button>
          </div>
          <button class="btn-secondary" style="width:100%" @click="toast('打开权限管理', 'info')">权限管理</button>
        </div>
      </div>
    </div>
  </aside>
</template>
