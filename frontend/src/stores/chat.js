// frontend/src/stores/chat.js
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { useNavStore } from '@/stores/nav' // 追加
import { usePosition } from '@/lib/usePosition' // 追加
import { sendChatMessage } from '@/lib/api'
import { sendSwMessage } from '@/lib/swClient' // 追加

export const useChatStore = defineStore('chat', () => {
  const userStore = useUserStore()
  const navStore = useNavStore() // 追加
  const position = usePosition() // 追加
  const { currentPos } = position // 追加

  // State
  const messages = ref([])
  const threadId = ref(null)
  const isLoading = ref(false)

  // Actions
  async function sendMessage(userInput) {
    if (!userInput.trim() || isLoading.value) return

    isLoading.value = true

    // 1. Add user message to the list
    messages.value.push({
      id: crypto.randomUUID(),
      text: userInput,
      sender: 'user',
      timestamp: new Date(),
    })

    try {
      // 2. Call the API
      const response = await sendChatMessage(
        userStore.userName,
        userInput,
        threadId.value || '' // Send empty string for the first message
      )

      // 3. Update threadId from the response
      if (response.thread_id) {
        threadId.value = response.thread_id
      }

      // 4. Add AI response to the list
      messages.value.push({
        id: crypto.randomUUID(),
        text: response.response_text,
        sender: 'ai',
        timestamp: new Date(),
        itinerary: response.itinerary || [],
      })

      // 5. If itinerary is present, trigger navigation plan
      if (response.itinerary && response.itinerary.length > 0) {
        if (!currentPos.value) {
          console.warn('Current position not available for navigation plan.')
          messages.value.push({
            id: crypto.randomUUID(),
            text: '現在地が取得できないため、ナビゲーションプランを作成できませんでした。',
            sender: 'system',
            timestamp: new Date(),
          })
          return // 現在地がない場合はナビプランを作成しない
        }

        const { lat, lng } = currentPos.value
        const planOptions = {
          language: response.language, // AIからのレスポンスの言語を使用
          origin: {
            lat,
            lon: lng
          },
          waypoints: response.itinerary.map((spot_id) => ({ spot_id: spot_id }))
        }

        await sendSwMessage({ type: 'RESET_TILES_CACHE' })
        await navStore.fetchRoute(planOptions, { navigate: false })
        // useNavWindow が navStore.plan を監視して自動で表示される
      }

    } catch (error) {
      console.error('Failed to send message or create navigation plan:', error)
      messages.value.push({
        id: crypto.randomUUID(),
        text: 'エラーが発生しました。メッセージを送信できませんでした。',
        sender: 'system',
        timestamp: new Date(),
      })
    } finally {
      isLoading.value = false
    }
  }

  function clearChat() {
    messages.value = []
    threadId.value = null
    navStore.clearPlan() // ナビプランもクリア
  }

  return {
    messages,
    threadId,
    isLoading,
    sendMessage,
    clearChat,
  }
})