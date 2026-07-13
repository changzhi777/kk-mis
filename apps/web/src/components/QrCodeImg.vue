<template>
  <canvas ref="canvasRef" :width="size" :height="size"></canvas>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    value: string
    size?: number
  }>(),
  { size: 200 },
)

const canvasRef = ref<HTMLCanvasElement>()

function render() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  // 简易 QR 占位（仅用于 UI 占位；生产应使用 qrcode.js / qrcode-generator）
  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, props.size, props.size)
  ctx.fillStyle = '#000'
  ctx.font = '12px monospace'
  ctx.textAlign = 'center'
  ctx.fillText(props.value.slice(0, 24), props.size / 2, props.size / 2)
  ctx.strokeRect(8, 8, props.size - 16, props.size - 16)
}

onMounted(render)
watch(() => props.value, render)
</script>