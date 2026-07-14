import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';
import AutoImport from 'unplugin-auto-import/vite';
import Components from 'unplugin-vue-components/vite';
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
// dev 修复：base='/oa/' 使前端 baseURL（/oa/admin 等）请求 path 含 /oa 前缀，
// 而 server.proxy key '/admin' 匹配 raw path → 不匹配 → 404。
// 此中间件在 proxy 之前注入（configureServer 不返回函数 = 前置），把 /oa 前缀去掉让原 proxy 匹配。
// prod 走 nginx（/oa/admin/ → :8300/admin/）不受影响。
var devStripOaPrefix = {
    name: 'dev-strip-oa-prefix',
    apply: 'serve',
    configureServer: function (server) {
        server.middlewares.use(function (req, _res, next) {
            if (req.url && /^\/oa\/(admin|api|llm)(\/|$)/.test(req.url)) {
                req.url = req.url.replace(/^\/oa/, '');
            }
            next();
        });
    },
};
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
        devStripOaPrefix,
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
            // admin（企业/财务/资产/代理/OA/CMS/office 桥，含 oa_agent_bridge 转发 :9001）
            '/admin': { target: 'http://localhost:8300', changeOrigin: true },
        },
    },
});
