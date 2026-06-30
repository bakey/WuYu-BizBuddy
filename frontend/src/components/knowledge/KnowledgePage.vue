<script setup>
import KnowledgeSidebar from './KnowledgeSidebar.vue'
import UploadZone       from './UploadZone.vue'
import DatasetTable     from './DatasetTable.vue'
import RetrievePanel    from './RetrievePanel.vue'
import IndustryKnowledgePanel from './IndustryKnowledgePanel.vue'
import { useKnowledgeStore } from '@/stores/knowledge'

const store = useKnowledgeStore()
</script>

<template>
  <div class="page-wrapper">
    <KnowledgeSidebar />
    <div class="kb-main">
      <!-- Page header with KPIs -->
      <div class="page-hdr" style="align-items:flex-start">
        <div>
          <h2>企业知识库</h2>
          <div class="page-hdr-sub">上传企业自有数据（工艺参数、项目报告、合同文档、遥感图像等），系统自动解析、清洗、建立向量索引，与公共数据源融合检索。</div>
        </div>
        <div class="kpi-grid" style="grid-template-columns:repeat(4,1fr);min-width:480px">
          <div class="kpi" style="padding:10px 14px">
            <div class="kpi-l">数据集</div>
            <div class="kpi-v" style="font-size:20px">{{ store.kpis.datasets }}</div>
          </div>
          <div class="kpi" style="padding:10px 14px">
            <div class="kpi-l">文档</div>
            <div class="kpi-v" style="font-size:20px">{{ store.kpis.docs }}</div>
          </div>
          <div class="kpi" style="padding:10px 14px">
            <div class="kpi-l">大小</div>
            <div class="kpi-v" style="font-size:20px">{{ store.kpis.size }}<span style="font-size:12px;color:var(--ink3)">GB</span></div>
          </div>
          <div class="kpi" style="padding:10px 14px">
            <div class="kpi-l">可用率</div>
            <div class="kpi-v" style="font-size:20px">{{ store.kpis.availability }}<span style="font-size:12px;color:var(--ink3)">%</span></div>
          </div>
        </div>
      </div>

      <UploadZone />
      <DatasetTable />
      <RetrievePanel />
      <IndustryKnowledgePanel />
    </div>
  </div>
</template>

<style scoped>
.kb-main { flex: 1; min-width: 0; padding: 16px; background: var(--bg); display: flex; flex-direction: column; gap: 14px; overflow-y: auto; }
.kpi-grid { display: grid; gap: 14px; }
</style>
