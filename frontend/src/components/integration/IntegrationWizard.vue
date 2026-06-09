<script setup>
import { useIntegrationStore } from '@/stores/integration'
import { useToast }            from '@/composables/useToast'

const store = useIntegrationStore()
const { toast } = useToast()

const fillPct = (steps) => {
  const doneCount = steps.filter(s => s.state === 'done').length
  return Math.round((doneCount / (steps.length - 1)) * 100)
}
</script>

<template>
  <div v-if="store.wizard.active" class="wiz">
    <div class="wiz-head">
      <div class="wiz-title">{{ store.wizard.title }}</div>
      <button class="btn-secondary" @click="store.dismissWizard">取消</button>
    </div>
    <div class="wiz-steps">
      <div class="wiz-line">
        <div class="fill" :style="{ width: fillPct(store.wizard.steps) + '%' }"></div>
      </div>
      <div
        v-for="(step, i) in store.wizard.steps"
        :key="i"
        class="wiz-step"
        :class="step.state"
      >
        <div class="num">{{ step.state === 'done' ? '✓' : i + 1 }}</div>
        <div class="lb">{{ step.label }}</div>
      </div>
    </div>
  </div>
</template>
