// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router';
import { useUserStore } from '@/stores/user';

const PlanView = () => import('@/views/PlanView.vue');
const NavView  = () => import('@/views/NavView.vue');
const LoginView = () => import('@/views/LoginView.vue');
const ChatView = () => import('@/views/ChatView.vue');

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/plan', name: 'plan', component: PlanView },
    { path: '/nav',  name: 'nav',  component: NavView  },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/chat', name: 'chat', component: ChatView, meta: { requiresAuth: true } },
  ],
});

router.beforeEach((to, from, next) => {
  // Piniaストアは`setup`外で呼び出すとエラーになる可能性があるため、
  // ガード内で直接インポートしたストア定義から状態を取得するのではなく、
  // main.jsでPiniaインスタンスが作成された後にストアにアクセスします。
  // ここでは、セッションストレージを直接確認する簡易的な方法を取ります。
  const user = sessionStorage.getItem('user');
  const isLoggedIn = !!user;

  // ログインが必要なページへのアクセスチェック
  if (to.matched.some(record => record.meta.requiresAuth)) {
    if (!isLoggedIn) {
      // 未ログインの場合はログインページにリダイレクト
      next({ name: 'login' });
    } else {
      next(); // ログイン済みの場合はそのまま表示
    }
  } else if (to.name === 'login' && isLoggedIn) {
    // ログイン済みでログインページにアクセスした場合はチャットページにリダイレクト
    next({ name: 'chat' });
  }
  else {
    next(); // 認証が不要なページはそのまま表示
  }
});

export default router;
