<!-- frontend/src/views/LoginView.vue -->
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
  errorMessage.value = '' // モード切り替え時にエラーメッセージをクリア
}

function getErrorMessage(error) {
  if (!error || !error.status) {
    return '不明なエラーが発生しました。'
  }
  switch (error.status) {
    case 404:
      return 'ユーザーが見つかりません。'
    case 409:
      return 'そのユーザー名は既に使用されています。'
    case 400:
      return '不正なリクエストです。入力内容を確認してください。'
    default:
      return `エラーが発生しました (コード: ${error.status})。`
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
    errorMessage.value = 'ユーザー名を入力してください。'
    return
  }
  isLoading.value = true
  errorMessage.value = ''
  const result = await userStore.login(userName.value.trim())
  isLoading.value = false
  if (result.success) {
    router.push('/chat')
  } else {
    errorMessage.value = getErrorMessage(result.error)
  }
}

async function performRegister() {
  if (!userName.value.trim()) {
    errorMessage.value = 'ユーザー名を入力してください。'
    return
  }
  isLoading.value = true
  errorMessage.value = ''
  const result = await userStore.register(userName.value.trim(), language.value)
  isLoading.value = false
  if (result.success) {
    router.push('/chat')
  } else {
    errorMessage.value = getErrorMessage(result.error)
  }
}
</script>

<template>
  <div class="login-container">
    <div class="login-box">
      <h2>{{ isLoginMode ? 'ログイン' : '新規登録' }}</h2>
      <form @submit.prevent="handleSubmit">
        <div class="input-group">
          <label for="username">ユーザー名</label>
          <input
            id="username"
            v-model="userName"
            type="text"
            placeholder="例: tanaka"
            required
            :disabled="isLoading"
          />
        </div>

        <!-- Language Selector (Register mode only) -->
        <div v-if="!isLoginMode" class="input-group">
          <label for="language">言語</label>
          <select id="language" v-model="language" :disabled="isLoading" class="language-select">
            <option value="ja">日本語</option>
            <option value="en">English</option>
            <option value="zh">中文</option>
          </select>
        </div>

        <button type="submit" class="button" :disabled="isLoading">
          {{ isLoading ? '処理中...' : (isLoginMode ? 'ログイン' : '新規登録') }}
        </button>

        <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
      </form>

      <div class="toggle-form">
        <p>
          {{ isLoginMode ? 'アカウントをお持ちでないですか？' : 'すでにアカウントをお持ちですか？' }}
          <a href="#" @click.prevent="toggleFormMode">
            {{ isLoginMode ? '新規登録' : 'ログイン' }}
          </a>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f0f2f5;
}
.login-box {
  width: 100%;
  max-width: 400px;
  padding: 40px;
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  text-align: center;
}
h2 {
  margin-bottom: 24px;
  color: #333;
}
.input-group {
  margin-bottom: 20px;
  text-align: left;
}
label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
  color: #555;
}
input,
.language-select {
  width: 100%;
  padding: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 16px;
  background-color: white;
}
.button {
  width: 100%;
  padding: 12px;
  background-color: #1d4ed8;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  cursor: pointer;
  transition: background-color 0.3s;
  margin-top: 10px;
}
.button:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}
.button:not(:disabled):hover {
  opacity: 0.9;
}
.error-message {
  color: #dc2626;
  margin-top: 15px;
  min-height: 1.2em;
}
.toggle-form {
  margin-top: 20px;
  font-size: 14px;
  color: #555;
}
.toggle-form a {
  color: #1d4ed8;
  text-decoration: none;
  font-weight: bold;
}
.toggle-form a:hover {
  text-decoration: underline;
}
</style>
