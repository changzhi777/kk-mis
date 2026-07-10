<template>
  <span>{{ formatted }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    value?: string | null
    fallback?: string
  }>(),
  { fallback: '-' }
)

const formatted = computed(() => {
  if (!props.value) return props.fallback
  const d = new Date(props.value)
  if (isNaN(d.getTime())) return props.fallback
  return d.toLocaleString('zh-CN')
})
</script>
