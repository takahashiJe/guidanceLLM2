// frontend/src/stores/chat.js
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { useNavStore } from '@/stores/nav'
import { sendChatMessage, getUserSession } from '@/lib/api' // Import getUserSession
import { sendSwMessage } from '@/lib/swClient'

const DEFAULT_ORIGIN = Object.freeze({ lat: 39.393477, lon: 140.073769 })

export const useChatStore = defineStore('chat', () => {
  const userStore = useUserStore()
  const navStore = useNavStore()

  // State
  const messages = ref([])
  const threadId = ref(null)
  const isLoading = ref(false)

  const isSessionLoaded = ref(false);

  // Actions
  async function sendMessage(userInput) {
    if (!userInput.trim() || isLoading.value) return

    isLoading.value = true

    // 1. Add user message to the list (using 'content')
    messages.value.push({
      id: crypto.randomUUID(),
      content: userInput,
      sender: 'user',
      timestamp: new Date(),
    })

    // 2. Add AI placeholder message for animation
    const aiPlaceholder = {
      id: crypto.randomUUID(),
      content: '',
      sender: 'ai',
      timestamp: new Date(),
      isPending: true, // This flag triggers the spinner
    };
    messages.value.push(aiPlaceholder);

    try {
      // 3. Call the API
      const response = await sendChatMessage(
        userStore.userName,
        userInput,
        threadId.value || ''
      )

      // 4. Update threadId from the response
      if (response.thread_id) {
        threadId.value = response.thread_id
      }

      // 5. Find the placeholder and update it with the AI response
      const placeholder = messages.value.find(m => m.id === aiPlaceholder.id);
      if (placeholder) {
        placeholder.content = response.response_text;
        placeholder.itinerary = response.itinerary || [];
        placeholder.isPending = false; // This triggers the text animation
      }

      // 6. If itinerary is present, trigger navigation plan
      if (response.itinerary && response.itinerary.length > 0) {
        const planOptions = {
          language: response.language,
          origin: DEFAULT_ORIGIN,
          waypoints: response.itinerary.map((spot_id) => ({ spot_id: spot_id }))
        }

        await sendSwMessage({ type: 'RESET_TILES_CACHE' })
        await navStore.fetchRoute(planOptions, { navigate: false })
      }

    } catch (error) {
      console.error('Failed to send message or create navigation plan:', error)
      // Find the placeholder and update it with an error message
      const placeholder = messages.value.find(m => m.id === aiPlaceholder.id);
      if (placeholder) {
        placeholder.content = 'エラーが発生しました。メッセージを送信できませんでした。';
        placeholder.isPending = false;
      }
    } finally {
      isLoading.value = false
    }
  }

  function clearChat() {
    console.log('[ChatStore] Clearing chat and navigation plan...');
    messages.value = []
    threadId.value = null
    isSessionLoaded.value = false; // Reset session loaded flag
    navStore.reset();
    console.log('[ChatStore] Chat and navigation plan cleared.');
  }

  async function rehydrateSession() {
    // Only run if user is logged in and session hasn't been loaded yet
    if (userStore.isLoggedIn && !isSessionLoaded.value) {
        console.log('[ChatStore rehydrateSession] Condition met, starting process...');
        isLoading.value = true;
        try {
            const userName = userStore.userName;
            console.log(`[ChatStore rehydrateSession] Fetching session for user: ${userName}`);
            const sessionData = await getUserSession(userName);
            console.log('[ChatStore rehydrateSession] Received data from API:', sessionData);

            if (sessionData && sessionData.chat_history && sessionData.chat_history.length > 0) {
                // Rehydrate chat messages
                messages.value = sessionData.chat_history.map(msg => ({
                    id: crypto.randomUUID(),
                    content: msg.content,
                    sender: msg.role === 'assistant' ? 'ai' : 'user', // handle role mapping
                    timestamp: new Date(msg.timestamp),
                }));
                console.log(`[ChatStore rehydrateSession] Rehydrated ${messages.value.length} messages.`);
            } else {
                console.log('[ChatStore rehydrateSession] No existing chat history found.');
                messages.value = []; // Ensure chat is empty if no history
            }

            // Rehydrate itinerary in nav store
            if (sessionData && sessionData.itinerary && sessionData.itinerary.length > 0) {
                console.log('[ChatStore rehydrateSession] Itinerary found, calling navStore.setItinerary...');
                navStore.setItinerary(sessionData.itinerary);
            } else {
                console.log('[ChatStore rehydrateSession] No itinerary found in session data.');
            }
            console.log('[ChatStore rehydrateSession] Session restoration attempt finished.');
        } catch (error) {
            console.error("[ChatStore rehydrateSession] Failed to rehydrate session:", error);
            messages.value = []; // Clear messages on error to allow welcome message
        } finally {
            isLoading.value = false;
            isSessionLoaded.value = true; // Mark session as loaded
            console.log(`[ChatStore rehydrateSession] isSessionLoaded set to true.`);
        }
    } else {
      console.log('[ChatStore rehydrateSession] Conditions not met. Skipping rehydration.', { isLoggedIn: userStore.isLoggedIn, isSessionLoaded: isSessionLoaded.value });
    }
  }

  return {
    messages,
    threadId,
    isLoading,
    isSessionLoaded,
    sendMessage,
    clearChat,
    rehydrateSession, // Expose the new action
  }
})
