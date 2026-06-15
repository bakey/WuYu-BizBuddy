<script setup>
const props = defineProps({
  show:  { type: Boolean, default: false },
  title: { type: String,  default: '' },
  large: { type: Boolean, default: false }
})
const emit = defineEmits(['close'])

function onMaskClick(e) {
  if (e.target === e.currentTarget) emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div class="modal-mask" :class="{ show }" @click="onMaskClick">
      <div class="modal" :class="{ lg: large }">
        <div class="modal-hdr">
          <div class="modal-title">
            <slot name="title">{{ title }}</slot>
          </div>
          <button class="modal-close" @click="emit('close')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <slot />
        </div>
        <div class="modal-foot" v-if="$slots.footer">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>
