import { ref } from 'vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export function useMissLogs() {
  const summary = ref({})
  const fonts = ref([])
  const urls = ref([])
  const fontDetail = ref(null)
  const urlDetail = ref(null)
  const glyphs = ref([])
  const loading = ref(false)

  const fetchSummary = async () => {
    const resp = await fetch(`${API_BASE_URL}/api/miss-logs/summary`)
    summary.value = await resp.json()
  }

  const fetchFonts = async (sort = 'last_seen', order = 'desc', q = '') => {
    loading.value = true
    try {
      const params = new URLSearchParams({ sort, order })
      if (q) params.set('q', q)
      const resp = await fetch(`${API_BASE_URL}/api/miss-logs/fonts?${params}`)
      fonts.value = await resp.json()
    } finally {
      loading.value = false
    }
  }

  const fetchUrls = async (sort = 'last_seen', order = 'desc') => {
    loading.value = true
    try {
      const resp = await fetch(`${API_BASE_URL}/api/miss-logs/urls?sort=${sort}&order=${order}`)
      urls.value = await resp.json()
    } finally {
      loading.value = false
    }
  }

  const fetchFontDetail = async (fontName, type = 'font') => {
    loading.value = true
    try {
      const resp = await fetch(`${API_BASE_URL}/api/miss-logs/fonts/detail`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ font_name: fontName, type }),
      })
      if (resp.ok) {
        fontDetail.value = await resp.json()
      } else {
        fontDetail.value = null
      }
    } finally {
      loading.value = false
    }
  }

  const fetchUrlDetail = async (url) => {
    loading.value = true
    try {
      const resp = await fetch(`${API_BASE_URL}/api/miss-logs/urls/detail`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      if (resp.ok) {
        urlDetail.value = await resp.json()
      } else {
        urlDetail.value = null
      }
    } finally {
      loading.value = false
    }
  }

  const fetchGlyphs = async (fontName) => {
    loading.value = true
    try {
      const resp = await fetch(`${API_BASE_URL}/api/miss-logs/glyphs?font=${encodeURIComponent(fontName)}`)
      glyphs.value = await resp.json()
    } finally {
      loading.value = false
    }
  }

  const fetchAllGlyphs = async (sort = 'total_count', order = 'desc', fontName = '') => {
    loading.value = true
    try {
      const params = new URLSearchParams({ sort, order })
      if (fontName) params.set('font', fontName)
      const resp = await fetch(`${API_BASE_URL}/api/miss-logs/glyphs?${params}`)
      glyphs.value = await resp.json()
    } finally {
      loading.value = false
    }
  }

  const deleteUrl = async (url) => {
    const resp = await fetch(`${API_BASE_URL}/api/miss-logs/urls/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })
    return resp.ok
  }

  const clearAll = async () => {
    const resp = await fetch(`${API_BASE_URL}/api/miss-logs/clear`, {
      method: 'DELETE',
    })
    return resp.ok
  }

  return {
    summary, fonts, urls, fontDetail, urlDetail, glyphs, loading,
    fetchSummary, fetchFonts, fetchUrls, fetchFontDetail,
    fetchUrlDetail, fetchGlyphs, fetchAllGlyphs,
    deleteUrl, clearAll,
  }
}
