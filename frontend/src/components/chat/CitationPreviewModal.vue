<script setup>
import BaseModal from '@/components/common/BaseModal.vue'
import { useCitationPreview } from '@/composables/useCitationPreview'
import { useToast } from '@/composables/useToast'
import { downloadText } from '@/utils/file'

const { previewItem, closePreview } = useCitationPreview()
const { toast } = useToast()

function onDownload() {
  const it = previewItem.value
  if (!it || !it.content) return
  const name = it.source || `引用-${it.num || it.id || 1}.txt`
  downloadText(name, it.content)
  toast(`已下载 ${name}`, 'ok')
}
</script>

<template>
  <BaseModal :show="!!previewItem" large @close="closePreview">
    <template #title>引用预览 · {{ previewItem?.source || '文档片段' }}</template>

    <div v-if="previewItem" class="cite-preview">
      <div class="cite-preview-meta">
        <span class="tag tag-blue">{{ previewItem.source || '文档片段' }}</span>
        <span v-if="previewItem.score != null" class="cite-score">
          相似度 {{ (previewItem.score * 100).toFixed(0) }}%
        </span>
      </div>
      <div class="cite-preview-content">{{ previewItem.content || '（该引用暂无可预览内容）' }}</div>
    </div>

    <template #footer>
      <button class="btn-secondary" @click="closePreview">关闭</button>
      <button class="btn-primary" :disabled="!previewItem?.content" @click="onDownload">下载原文</button>
    </template>
  </BaseModal>
</template>

<style scoped>
.cite-preview-meta {
  display: flex; align-items: center; gap: 10px; margin-bottom: 12px;
}
.cite-score { font-size: 12px; color: var(--ink3); }
.cite-preview-content {
  white-space: pre-wrap; line-height: 1.85; font-size: 13px; color: var(--ink);
  background: var(--surface2); border: 1px solid var(--line); border-radius: 8px;
  padding: 14px; max-height: 52vh; overflow-y: auto;
}
</style>
