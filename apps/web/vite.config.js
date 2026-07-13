import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';
import AutoImport from 'unplugin-auto-import/vite';
import Components from 'unplugin-vue-components/vite';
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
export default defineConfig({
    base: '/oa/',
    plugins: [
        vue(),
        // 自动按需导入 EP API（ElMessage 等）+ vue/vue-router/pinia
        AutoImport({
            imports: ['vue', 'vue-router', 'pinia'],
            resolvers: [ElementPlusResolver({ importStyle: 'sass' })],
            dts: 'src/types/auto-imports.d.ts',
        }),
        // 自动按需注册 EP 组件
        Components({
            resolvers: [ElementPlusResolver({ importStyle: 'sass' })],
            dts: 'src/types/components.d.ts',
        }),
    ],
    resolve: {
        alias: {
            '@': fileURLToPath(new URL('./src', import.meta.url)),
        },
    },
    css: {
        preprocessorOptions: {
            scss: {
                // 全局注入 EP 变量覆盖（编译期主题色生效）
                additionalData: "@use \"@/styles/element/_variables.scss\" as *;",
            },
        },
    },
    server: {
        port: 5173,
        host: '0.0.0.0',
        proxy: {
            // meeting-notes（音频上传 / ASR / LLM）
            '/api': { target: 'http://localhost:8000', changeOrigin: true },
            '/llm': { target: 'http://localhost:8000', changeOrigin: true },
            // admin（企业/财务/资产/代理/OA，含 oa-agent bridge → :9001）
            // dev 时需要同时启动 admin :8300（已含 oa_agent_bridge 转发到 :9001）
            '/admin': { target: 'http://localhost:8300', changeOrigin: true },
        },
    },
});
