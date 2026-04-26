import { ref, onMounted, onBeforeUnmount } from 'vue'

export function useSSE(url) {
  const messages = ref([])
  const connected = ref(false)
  let eventSource = null
  let reconnectTimer = null

  const connect = () => {
    if (eventSource) {
      eventSource.close()
    }

    eventSource = new EventSource(url)

    eventSource.onopen = () => {
      connected.value = true
    }

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        messages.value.push(data)
        // Keep last 500 messages
        if (messages.value.length > 500) {
          messages.value = messages.value.slice(-500)
        }
      } catch {
        // Ignore parse errors (keepalive comments etc)
      }
    }

    eventSource.onerror = () => {
      connected.value = false
      eventSource.close()
      eventSource = null
      // Auto-reconnect after 3s
      reconnectTimer = setTimeout(connect, 3000)
    }
  }

  const disconnect = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    connected.value = false
  }

  const clearMessages = () => {
    messages.value = []
  }

  onMounted(connect)
  onBeforeUnmount(disconnect)

  return { messages, connected, clearMessages, reconnect: connect, disconnect }
}
