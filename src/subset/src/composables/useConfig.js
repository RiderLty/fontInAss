import { ref } from 'vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export function useConfig() {
  const config = ref({})
  const loading = ref(false)

  const fetchConfig = async () => {
    loading.value = true
    try {
      const resp = await fetch(`${API_BASE_URL}/api/config`)
      config.value = await resp.json()
    } catch (e) {
      console.error('Failed to fetch config:', e)
    } finally {
      loading.value = false
    }
  }

  const updateConfig = async (key, value) => {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value }),
      })
      const result = await resp.json()
      if (result.success) {
        await fetchConfig()
      }
      return result
    } catch (e) {
      console.error('Failed to update config:', e)
      return { success: false, error: e.message }
    }
  }

  const deleteConfig = async (key) => {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/config/${key}`, {
        method: 'DELETE',
      })
      const result = await resp.json()
      if (result.success) {
        await fetchConfig()
      }
      return result
    } catch (e) {
      console.error('Failed to delete config:', e)
      return { success: false, error: e.message }
    }
  }

  return { config, loading, fetchConfig, updateConfig, deleteConfig }
}
