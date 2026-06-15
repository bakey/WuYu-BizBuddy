import { ref } from 'vue'

const toasts = ref([])
let _id = 0

export function useToast() {
  function toast(msg, type = 'ok', duration = 2400) {
    const id = ++_id
    toasts.value.push({ id, msg, type })
    setTimeout(() => {
      const idx = toasts.value.findIndex(t => t.id === id)
      if (idx > -1) toasts.value.splice(idx, 1)
    }, duration)
  }

  return { toasts, toast }
}
