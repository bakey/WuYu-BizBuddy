<script setup>
import { useIntegrationStore } from '@/stores/integration'
const store = useIntegrationStore()
</script>

<template>
  <div class="integ-buckets">
    <!-- Government -->
    <div class="integ-bucket">
      <div class="integ-bucket-head">
        <div class="integ-bucket-ic" style="background:var(--info-light);color:var(--info);font-size:22px">🏛️</div>
        <div class="integ-bucket-info">
          <h3>政府数据平台 <span class="tag tag-blue">8 个</span></h3>
          <p>对接生态环境部、国家统计局、海关总署、各省固废监管平台。提供权威数据自动同步与溯源审计。</p>
        </div>
      </div>
      <div class="integ-bucket-stats">
        <div class="integ-bucket-stat"><div class="v">{{ store.govBucket.connected }}</div><div class="l">已接入</div></div>
        <div class="integ-bucket-stat"><div class="v">{{ store.govBucket.pending }}</div><div class="l">待授权</div></div>
        <div class="integ-bucket-stat"><div class="v">{{ store.govBucket.daily }}</div><div class="l">日新增</div></div>
        <div class="integ-bucket-stat"><div class="v">{{ store.govBucket.successRate }}</div><div class="l">同步成功率</div></div>
      </div>
    </div>

    <!-- Enterprise -->
    <div class="integ-bucket">
      <div class="integ-bucket-head">
        <div class="integ-bucket-ic" style="background:#FEF3C7;color:var(--warn);font-size:22px">🏢</div>
        <div class="integ-bucket-info">
          <h3>企业内部系统 <span class="tag tag-orange">12 个</span></h3>
          <p>SAP/用友/金蝶 ERP、MES 生产系统、钉钉/飞书工作台、自定义 REST/GraphQL API。提供加密通道与多租户隔离。</p>
        </div>
      </div>
      <div class="integ-bucket-stats">
        <div class="integ-bucket-stat"><div class="v">{{ store.entBucket.connected }}</div><div class="l">已接入</div></div>
        <div class="integ-bucket-stat"><div class="v">{{ store.entBucket.configuring }}</div><div class="l">配置中</div></div>
        <div class="integ-bucket-stat"><div class="v">{{ store.entBucket.syncSize }}</div><div class="l">日同步量</div></div>
        <div class="integ-bucket-stat"><div class="v">{{ store.entBucket.tenants }}</div><div class="l">活跃租户</div></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.integ-buckets { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.integ-bucket { background: var(--surface); border-radius: var(--radius); border: 1px solid var(--line); box-shadow: var(--shadow-card); padding: 18px; }
.integ-bucket-head { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 14px; }
.integ-bucket-ic { width: 48px; height: 48px; border-radius: 12px; display: grid; place-items: center; flex-shrink: 0; }
.integ-bucket-info h3 { font-size: 15px; font-weight: 700; margin-bottom: 4px; display: flex; align-items: center; gap: 8px; }
.integ-bucket-info p { font-size: 12px; color: var(--ink3); line-height: 1.55; }
.integ-bucket-stats { display: flex; gap: 20px; padding-top: 14px; border-top: 1px solid var(--line); }
.integ-bucket-stat .v { font-size: 20px; font-weight: 700; color: var(--ink); letter-spacing: -.3px; }
.integ-bucket-stat .l { font-size: 10px; color: var(--ink4); margin-top: 2px; }
</style>
