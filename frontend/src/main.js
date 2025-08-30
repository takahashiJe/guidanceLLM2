import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import { router } from "./router";

// ベースCSSの読み込み
import "./assets/base.css";
import "./assets/main.css";

const app = createApp(App);

// 状態管理（Pinia）
const pinia = createPinia();
app.use(pinia);

// ルーティング
app.use(router);

// マウント
app.mount("#app");
