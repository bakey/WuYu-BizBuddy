import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const activeTab = ref('chat')

  function setTab(tab) {
    activeTab.value = tab
  }

  return { activeTab, setTab }
})
