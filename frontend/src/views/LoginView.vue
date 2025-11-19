<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const formMode = ref('login') // 'login' or 'register'
const userName = ref('')
const language = ref('ja')
const isLoading = ref(false)
const errorMessage = ref('')
const router = useRouter()
const userStore = useUserStore()

const isLoginMode = computed(() => formMode.value === 'login')

function toggleFormMode() {
  formMode.value = isLoginMode.value ? 'register' : 'login'
  errorMessage.value = ''
}

function getErrorMessage(error) {
  if (!error || !error.status) return '不明なエラーが発生しました。'
  switch (error.status) {
    case 404: return 'ユーザーが見つかりません。';
    case 409: return 'そのユーザー名は既に使用されています。';
    case 400: return '不正なリクエストです。入力内容を確認してください。';
    default: return `エラーが発生しました (コード: ${error.status})。`;
  }
}

async function handleSubmit() {
  if (isLoginMode.value) {
    await performLogin()
  } else {
    await performRegister()
  }
}

async function performLogin() {
  if (!userName.value.trim()) {
    errorMessage.value = 'ユーザー名を入力してください。';
    return;
  }
  isLoading.value = true;
  errorMessage.value = '';
  const result = await userStore.login(userName.value.trim());
  isLoading.value = false;
  if (result.success) {
    router.push('/app/chat');
  } else {
    errorMessage.value = getErrorMessage(result.error);
  }
}

async function performRegister() {
  if (!userName.value.trim()) {
    errorMessage.value = 'ユーザー名を入力してください。';
    return;
  }
  isLoading.value = true;
  errorMessage.value = '';
  const result = await userStore.register(userName.value.trim(), language.value);
  isLoading.value = false;
  if (result.success) {
    formMode.value = 'login';
    errorMessage.value = '登録が完了しました。ログインしてください。';
  } else {
    errorMessage.value = getErrorMessage(result.error);
  }
}
</script>

<template>
  <div class="tw-relative tw-flex tw-min-h-screen tw-w-full tw-items-center tw-justify-center tw-overflow-hidden tw-p-4">
    <!-- Background Image and Overlay -->
    <div class="tw-absolute tw-inset-0 tw-z-0 tw-bg-cover tw-bg-center" style="background-image: url('/chokai.jpg')"></div>
    <div class="tw-absolute tw-inset-0 tw-z-0 tw-bg-gradient-to-b tw-from-black/90 tw-via-black/60 tw-to-transparent"></div>

    <!-- Absolutely Positioned Title -->
    <div class="tw-absolute tw-top-0 tw-left-0 tw-right-0 tw-z-10 tw-pt-24 sm:tw-pt-32">
      <div class="tw-w-full tw-max-w-md tw-mx-auto tw-px-4 animate-pop-in" style="animation-delay: 0.2s;">
        <h1 class="tw-text-5xl tw-font-bold tw-text-white" style="text-shadow: 1px 1px 10px rgba(0,0,0,0.5);">
          Chokai Guidance
          <span class="tw-block tw-text-3xl tw-font-light tw-tracking-wider tw-mt-2">by LLM</span>
        </h1>
      </div>
    </div>

    <!-- Centered Login Panel -->
    <div class="tw-relative tw-z-10 tw-w-full tw-max-w-md tw-mt-32 animate-fade-in-up" style="animation-delay: 0.4s;">
      <!-- Glass Panel -->
      <div class="tw-rounded-2xl tw-border tw-border-slate-700 tw-bg-slate-800/60 tw-p-8 tw-backdrop-blur-lg md:tw-p-10">
        <div class="tw-text-center">
          <h1 class="tw-text-3xl tw-font-bold tw-text-white md:tw-text-4xl">{{ isLoginMode ? 'Welcome Back' : 'Create Account' }}</h1>
          <p class="tw-mt-2 tw-text-slate-400">{{ isLoginMode ? 'Enter your username to continue' : 'Join the platform' }}</p>
        </div>

        <form @submit.prevent="handleSubmit" class="tw-mt-8 tw-space-y-6">
          <div class="tw-space-y-4">
            <!-- Username Input -->
            <div class="tw-relative">
              <input
                id="username"
                v-model="userName"
                type="text"
                placeholder="Username"
                required
                :disabled="isLoading"
                class="tw-peer tw-w-full tw-rounded-lg tw-border tw-border-slate-700 tw-bg-slate-900/70 tw-px-4 tw-py-3 tw-text-white placeholder:tw-text-slate-500 tw-transition-colors focus:tw-border-blue-500 focus:tw-outline-none focus:tw-ring-2 focus:tw-ring-blue-500/50"
              />
            </div>

            <!-- Language Selector (Register mode only) -->
            <div v-if="!isLoginMode" class="tw-relative">
              <select id="language" v-model="language" :disabled="isLoading" class="tw-w-full tw-rounded-lg tw-border tw-border-slate-700 tw-bg-slate-900/70 tw-px-4 tw-py-3 tw-text-white tw-transition-colors focus:tw-border-blue-500 focus:tw-outline-none focus:tw-ring-2 focus:tw-ring-blue-500/50">
                <option value="ja">日本語</option>
                <option value="en">English</option>
                <option value="zh">中文</option>
              </select>
            </div>
          </div>

          <!-- Error Message -->
          <div v-if="errorMessage" class="tw-rounded-md tw-bg-red-500/10 tw-p-3 tw-text-center tw-text-sm tw-text-red-400">
            {{ errorMessage }}
          </div>

          <!-- Submit Button -->
          <button type="submit" :disabled="isLoading" class="tw-w-full tw-rounded-lg tw-bg-blue-600 tw-px-5 tw-py-3 tw-text-base tw-font-semibold tw-text-white tw-transition-all hover:tw-bg-blue-700 active:tw-scale-95 disabled:tw-cursor-not-allowed disabled:tw-bg-slate-600">
            <span v-if="isLoading">Processing...</span>
            <span v-else>{{ isLoginMode ? 'Login' : 'Create Account' }}</span>
          </button>

          <!-- Toggle Form Mode -->
          <div class="tw-text-center tw-text-sm tw-text-slate-400">
            <p>
              {{ isLoginMode ? "Don't have an account?" : 'Already have an account?' }}
              <a href="#" @click.prevent="toggleFormMode" class="tw-font-medium tw-text-blue-400 tw-transition-colors hover:tw-text-blue-300">
                {{ isLoginMode ? 'Sign up' : 'Log in' }}
              </a>
            </p>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Pop-in animation for the title */
@keyframes fadeInScale {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.animate-pop-in {
  opacity: 0;
  transform: scale(0.95);
  animation: fadeInScale 0.7s ease-out forwards;
  animation-fill-mode: both;
}

/* Fade-in-up animation for the panel */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in-up {
  opacity: 0;
  transform: translateY(20px);
  animation: fadeInUp 0.8s ease-out forwards;
  animation-fill-mode: both;
}
</style>
