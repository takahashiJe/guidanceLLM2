<!-- frontend/src/views/ChatView.vue -->
<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { useUserStore } from '@/stores/user'
import { useChatStore } from '@/stores/chat'

import NavWindow from '@/components/NavWindow.vue'

const userStore = useUserStore()
const chatStore = useChatStore()

const { messages, isLoading } = storeToRefs(chatStore)
const userInput = ref('')

const messageContainer = ref(null)

function handleLogout() {
  userStore.logout()
  chatStore.clearChat()
}

async function handleSendMessage() {
  if (!userInput.value.trim()) return
  const text = userInput.value
  userInput.value = ''
  await chatStore.sendMessage(text)
  // Scroll to the bottom after message is sent and DOM is updated
  await nextTick()
  if (messageContainer.value) {
    messageContainer.value.scrollTop = messageContainer.value.scrollHeight
  }
}

// Add a welcome message on component mount if there are no messages
onMounted(() => {
  if (messages.value.length === 0) {
    messages.value.push({
      id: 'initial-welcome',
      text: `こんにちは、${userStore.userName}さん。どのようなご用件でしょうか？`,
      sender: 'ai',
      timestamp: new Date(),
    })
  }
})

// アバターのアイコン
const userAvatar = '👤'
const aiAvatar = '🤖'
const systemAvatar = 'ℹ️'

function getAvatar(sender) {
  if (sender === 'user') return userAvatar
  if (sender === 'ai') return aiAvatar
  return systemAvatar
}

function getSenderName(sender) {
  if (sender === 'user') return userStore.userName
  if (sender === 'ai') return 'AIエージェント'
  return 'システム'
}
</script>

<template>
  <div class="chat-container">
    <header class="chat-header">
      <h1 class="chat-title">AIエージェント</h1>
      <div class="user-profile">
        <span class="user-name">{{ userStore.userName }}</span>
        <button @click="handleLogout" class="logout-button">ログアウト</button>
      </div>
    </header>

    <main class="message-list" ref="messageContainer">
      <div
        v-for="message in messages"
        :key="message.id"
        class="message-item"
        :class="`message-item--${message.sender}`"
      >
        <div class="message-avatar" :class="`message-avatar--${message.sender}`">
          {{ getAvatar(message.sender) }}
        </div>
        <div class="message-content">
          <div class="message-sender-name">{{ getSenderName(message.sender) }}</div>
          <div class="message-bubble" :class="`message-bubble--${message.sender}`">
            <p>{{ message.text }}</p>
          </div>
          <div class="message-timestamp">
            {{ new Date(message.timestamp).toLocaleTimeString() }}
          </div>
        </div>
      </div>
      <div v-if="isLoading" class="message-item message-item--ai">
        <div class="message-avatar message-avatar--ai">
          {{ aiAvatar }}
        </div>
        <div class="message-content">
          <div class="message-sender-name">AIエージェント</div>
          <div class="message-bubble message-bubble--ai is-loading">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    </main>

    <footer class="chat-input-area">
      <form @submit.prevent="handleSendMessage" class="input-form">
        <textarea
          v-model="userInput"
          placeholder="メッセージを入力..."
          class="input-textarea"
          :disabled="isLoading"
          @keydown.enter.exact.prevent="handleSendMessage"
        ></textarea>
        <button type="submit" class="send-button" :disabled="isLoading || !userInput.trim()">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="send-icon">
            <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
          </svg>
        </button>
      </form>
    </footer>
  </div>
  <NavWindow />
</template>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #f7f8fa; /* Light background */
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  color: #333;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  background-color: #2c3e50; /* Darker header */
  color: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  flex-shrink: 0;
}

.chat-title {
  font-size: 1.4rem;
  margin: 0;
  font-weight: 600;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 15px;
}

.user-name {
  font-size: 1rem;
  font-weight: 500;
}

.logout-button {
  padding: 8px 15px;
  background-color: #e74c3c; /* Red for logout */
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  transition: background-color 0.3s ease;
  font-size: 0.9rem;
}

.logout-button:hover {
  background-color: #c0392b;
}

.message-list {
  flex-grow: 1;
  overflow-y: auto;
  padding: 0 15px;
  display: flex;
  flex-direction: column;
  gap: 15px;
  background-color: #f7f8fa;
}

.message-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  max-width: 100%; /* Limit message width */
}

.message-item--user {
  align-self: flex-end;
  flex-direction: row-reverse; /* User message on right */
}

.message-item--ai, .message-item--system {
  align-self: flex-start;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 1.2rem;
  background-color: #ecf0f1; /* Light gray avatar background */
  flex-shrink: 0;
}

.message-avatar--user {
  background-color: #3498db; /* Blue for user avatar */
  color: white;
}

.message-avatar--ai {
  background-color: #2ecc71; /* Green for AI avatar */
  color: white;
}

.message-avatar--system {
  background-color: #f1c40f; /* Yellow for system avatar */
  color: white;
}

.message-content {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.message-item--user .message-content {
  align-items: flex-end;
}

.message-sender-name {
  font-size: 0.85rem;
  color: #7f8c8d;
  margin-bottom: 4px;
}

.message-bubble {
  padding: 12px 18px;
  border-radius: 20px;
  word-wrap: break-word;
  white-space: pre-wrap; /* Preserve whitespace and line breaks */
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  line-height: 1.5;
}

.message-bubble p {
  margin: 0;
}

.message-bubble--user {
  background-color: #3498db; /* Blue bubble for user */
  color: white;
  border-bottom-right-radius: 4px; /* Pointy corner */
}

.message-bubble--ai {
  background-color: #ffffff; /* White bubble for AI */
  color: #333;
  border: 1px solid #e0e0e0;
  border-bottom-left-radius: 4px; /* Pointy corner */
}

.message-bubble--system {
  background-color: #fef08a; /* Light yellow for system */
  color: #92400e;
  border: 1px solid #fcd34d;
  text-align: center;
  border-radius: 10px;
  font-size: 0.9rem;
}

.message-timestamp {
  font-size: 0.75rem;
  color: #95a5a6;
  margin-top: 5px;
}

.chat-input-area {
  padding: 0;
  background-color: #ffffff;
  border-top: 1px solid #e0e0e0;
  flex-shrink: 0;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.05);
}

.input-form {
  display: flex;
  align-items: flex-end; /* Align items to bottom for textarea */
  gap: 10px;
  width: 100%;
  padding: 10px 15px;
}

.input-textarea {
  flex-grow: 1;
  padding: 12px 15px;
  border: 1px solid #bdc3c7;
  border-radius: 25px; /* Rounded input */
  font-size: 1rem;
  resize: none;
  min-height: 45px;
  max-height: 150px; /* Limit height */
  overflow-y: auto;
  transition: border-color 0.3s ease;
}

.input-textarea:focus {
  border-color: #3498db;
  outline: none;
}

.send-button {
  width: 45px;
  height: 45px;
  background-color: #3498db; /* Blue send button */
  color: white;
  border: none;
  border-radius: 50%; /* Circular button */
  cursor: pointer;
  transition: background-color 0.3s ease, transform 0.1s ease;
  display: flex;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;
}

.send-button:hover:not(:disabled) {
  background-color: #2980b9;
}

.send-button:active:not(:disabled) {
  transform: scale(0.95);;
}

.send-button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}

.send-icon {
  width: 20px;
  height: 20px;
}

/* Loading dots animation */
.message-bubble.is-loading {
  display: flex;
  gap: 4px;
  background-color: #e0e0e0;
  border: none;
  box-shadow: none;
}
.message-bubble.is-loading span {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #95a5a6;
  animation: loading-dots 1.4s infinite ease-in-out both;
}
.message-bubble.is-loading span:nth-child(1) {
  animation-delay: -0.32s;
}
.message-bubble.is-loading span:nth-child(2) {
  animation-delay: -0.16s;
}
@keyframes loading-dots {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}
</style>
