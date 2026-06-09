<script setup>
import { ref } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useToast }          from '@/composables/useToast'

const store  = useKnowledgeStore()
const { toast } = useToast()
const isDragOver = ref(false)

function onDragover(e) {
  e.preventDefault()
  isDragOver.value = true
}

function onDragleave() {
  isDragOver.value = false
}

function onDrop(e) {
  e.preventDefault()
  isDragOver.value = false
  const files = Array.from(e.dataTransfer?.files || [])
  if (!files.length) { toast('请拖入有效文件', 'warn'); return }
  files.forEach(f => store.addDataset(f))
  toast(`已添加 ${files.length} 个文件，开始解析…`, 'info')
}

function onClick() {
  toast('点击上传：请用拖拽功能演示效果 :)', 'info')
}

const FORMATS = ['CSV', 'Excel', 'JSON', 'PDF', 'Word', 'TXT', 'ZIP 批量包']
</script>

<template>
  <div
    class="upload-zone-big"
    :class="{ 'drag-over': isDragOver }"
    @dragover="onDragover"
    @dragleave="onDragleave"
    @drop="onDrop"
    @click="onClick"
  >
    <div class="uz-ic">
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
        <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
      </svg>
    </div>
    <div class="uz-t">拖拽文件到此处，或点击上传</div>
    <div class="uz-d">支持批量上传企业自有数据，系统将自动解析、清洗并建立索引</div>
    <div class="uz-formats">
      <span v-for="f in FORMATS" :key="f" class="fmt">{{ f }}</span>
    </div>
  </div>
</template>
