<script setup>
import { useDatabaseStore } from '@/stores/database'
import { useToast }         from '@/composables/useToast'

const store  = useDatabaseStore()
const { toast } = useToast()
</script>

<template>
  <div class="card">
    <div class="card-hdr">
      <div class="card-accent card-accent--purple"></div>
      <span class="card-title">数据治理任务</span>
      <button class="btn-text" @click="toast('查看全部任务', 'info')">查看全部</button>
    </div>
    <div class="card-body">
      <div class="clean-list">
        <div
          v-for="task in store.governanceTasks"
          :key="task.id"
          class="clean-task"
        >
          <div class="clean-ic" :style="{ background: task.iconBg, color: task.iconColor }">
            {{ task.icon }}
          </div>
          <div class="clean-info">
            <div class="ti">{{ task.title }}</div>
            <div class="ds">{{ task.desc }}</div>
            <div v-if="task.progress !== null" class="clean-prog">
              <div class="clean-prog-track">
                <div class="clean-prog-fill" :style="{ width: task.progress + '%' }"></div>
              </div>
              <span class="clean-pct" :style="{ color: task.progress === 100 ? 'var(--primary)' : 'var(--ink2)' }">
                {{ task.progress === 100 ? '完成' : task.progress + '%' }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.clean-list { display: flex; flex-direction: column; gap: 8px; }
</style>
