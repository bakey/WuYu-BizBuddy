import { ref } from 'vue'

// 引用预览单例：任意位置（消息内角标 / 右栏引用）点击都打开同一个预览框
const previewItem = ref(null)

export function useCitationPreview() {
  function openPreview(item) {
    previewItem.value = item
  }
  function closePreview() {
    previewItem.value = null
  }
  return { previewItem, openPreview, closePreview }
}
