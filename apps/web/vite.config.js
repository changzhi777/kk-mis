import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';
import AutoImport from 'unplugin-auto-import/vite';
import Components from 'unplugin-vue-components/vite';
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
export default defineConfig({
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
            '/api': { target: 'http://localhost:8000', changeOrigin: true },
            '/llm': { target: 'http://localhost:8000', changeOrigin: true },
        },
    },
});
