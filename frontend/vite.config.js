import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "node:path";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: '0.0.0.0', 
    port: 5173,
    proxy: {
      // フロントからの /api/* を APIゲートウェイ(8080)へ転送
      "/api": {
        target: "http://localhost:8080", // ゲートウェイが 0.0.0.0:8080 でも、ブラウザからは localhost 指定でOK
        changeOrigin: true,
        // パス書き換え不要（/api/nav/plan -> /api/nav/plan のまま）
        // rewrite: (p) => p.replace(/^\/api/, "/api"),
      },
    },
    hmr: {
      host: 'localhost'
    },
  },
});
