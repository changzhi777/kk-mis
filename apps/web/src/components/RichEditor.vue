<template>
  <div class="rich-editor">
    <div v-if="editor" class="toolbar">
      <el-button-group>
        <el-button size="small" :type="editor.isActive('bold') ? 'primary' : ''" @click="cmd((c) => c.toggleBold().run())"><b>B</b></el-button>
        <el-button size="small" :type="editor.isActive('italic') ? 'primary' : ''" @click="cmd((c) => c.toggleItalic().run())"><i>I</i></el-button>
        <el-button size="small" :type="editor.isActive('strike') ? 'primary' : ''" @click="cmd((c) => c.toggleStrike().run())"><s>S</s></el-button>
      </el-button-group>
      <el-button-group>
        <el-button size="small" :type="editor.isActive('heading', { level: 2 }) ? 'primary' : ''" @click="cmd((c) => c.toggleHeading({ level: 2 }).run())">H2</el-button>
        <el-button size="small" :type="editor.isActive('heading', { level: 3 }) ? 'primary' : ''" @click="cmd((c) => c.toggleHeading({ level: 3 }).run())">H3</el-button>
      </el-button-group>
      <el-button-group>
        <el-button size="small" :type="editor.isActive('bulletList') ? 'primary' : ''" @click="cmd((c) => c.toggleBulletList().run())">无序列表</el-button>
        <el-button size="small" :type="editor.isActive('orderedList') ? 'primary' : ''" @click="cmd((c) => c.toggleOrderedList().run())">有序列表</el-button>
      </el-button-group>
      <el-button size="small" @click="cmd((c) => c.undo().run())">撤销</el-button>
      <el-button size="small" @click="cmd((c) => c.redo().run())">重做</el-button>
    </div>
    <EditorContent :editor="editor" class="content" />
  </div>
</template>

<script setup lang="ts">
/**
 * TipTap 富文本编辑器封装（v-model 双向 + DOMPurify 净化输出防 XSS）。
 * 复用项目 XSS 防护模式（参考 OaAgent.vue 的 DOMPurify 用法）。
 */
import { onBeforeUnmount, watch } from 'vue'
import { EditorContent, useEditor } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import DOMPurify from 'dompurify'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const editor = useEditor({
  content: props.modelValue || '',
  extensions: [StarterKit],
  onUpdate: ({ editor }) => {
    // 输出 HTML 经 DOMPurify 净化（防 XSS，复用项目防护模式）
    emit('update:modelValue', DOMPurify.sanitize(editor.getHTML()))
  },
})

/** 执行编辑器链式命令（editor 可能 undefined，统一守卫） */
function cmd(fn: (chain: ReturnType<NonNullable<ReturnType<typeof useEditor>['value']>['chain']>) => void) {
  const e = editor.value
  if (e) fn(e.chain().focus())
}

// 外部 modelValue 变更同步到编辑器（加载/重置）
watch(
  () => props.modelValue,
  (val) => {
    if (editor.value && val !== editor.value.getHTML()) {
      editor.value.commands.setContent(val || '', { emitUpdate: false })
    }
  }
)

onBeforeUnmount(() => editor.value?.destroy())
</script>

<style scoped>
.rich-editor { border: 1px solid var(--el-border-color); border-radius: 4px; background: var(--el-bg-color); }
.toolbar { display: flex; gap: 8px; padding: 6px; border-bottom: 1px solid var(--el-border-color); flex-wrap: wrap; }
.content { min-height: 220px; }
.content :deep(.tiptap) { padding: 10px 12px; outline: none; min-height: 220px; }
.content :deep(.tiptap):focus { outline: none; }
.content :deep(h2) { font-size: 1.3em; margin: 0.6em 0 0.3em; }
.content :deep(h3) { font-size: 1.1em; margin: 0.5em 0 0.3em; }
.content :deep(ul), .content :deep(ol) { padding-left: 1.5em; }
.content :deep(p) { margin: 0.4em 0; }
</style>
