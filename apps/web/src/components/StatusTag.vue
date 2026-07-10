<template>
  <el-tag :type="meta.type || undefined" :size="size" :effect="effect">{{ meta.text }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getStatusMeta } from '@/composables/useMeetingStatus'

const props = withDefaults(
  defineProps<{
    status?: string
    size?: 'small' | 'default' | 'large'
    effect?: 'light' | 'dark' | 'plain'
  }>(),
  { size: 'small', effect: 'light' }
)

const meta = computed(() => getStatusMeta(props.status))
</script>
