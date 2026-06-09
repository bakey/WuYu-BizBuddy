<script setup>
import IntegrationSidebar from './IntegrationSidebar.vue'
import IntegrationBucket  from './IntegrationBucket.vue'
import IntegrationWizard  from './IntegrationWizard.vue'
import IntegrationList    from './IntegrationList.vue'
import IntegrationModal   from './IntegrationModal.vue'
import { ref } from 'vue'

const showModal = ref(false)
</script>

<template>
  <div class="page-wrapper">
    <IntegrationSidebar @add="showModal = true" />
    <div class="integ-main">
      <div class="page-hdr">
        <div>
          <h2>数据接入</h2>
          <div class="page-hdr-sub">将政府开放数据、企业内部系统、第三方平台一站式接入云数据库，支持 OAuth、API、数据库直连、文件同步多种方式。</div>
        </div>
        <div class="row">
          <button class="btn-secondary">批量导入</button>
          <button class="btn-secondary">查看 API 文档</button>
        </div>
      </div>

      <IntegrationBucket />
      <IntegrationWizard />
      <IntegrationList @add="showModal = true" />
    </div>
    <IntegrationModal :show="showModal" @close="showModal = false" />
  </div>
</template>

<style scoped>
.integ-main { flex: 1; min-width: 0; padding: 16px; background: var(--bg); display: flex; flex-direction: column; gap: 14px; overflow-y: auto; }
</style>
