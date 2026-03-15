import axios from 'axios'
import { message } from 'antd'

function clearAuthAndRedirect() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  // Lazy import to avoid circular dependency in tests
  import('@/stores/useAuthStore').then(({ useAuthStore }) => {
    useAuthStore.getState().logout()
  })
  window.location.href = '/login'
}

const client = axios.create({
  baseURL: '',
  timeout: 30000,
})

// Request deduplication for identical GET requests in flight
const inflightRequests = new Map<string, Promise<unknown>>()

function getRequestKey(config: { method?: string; url?: string; params?: unknown }) {
  if (config.method !== 'get') return null
  return `${config.url}|${JSON.stringify(config.params || {})}`
}

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let isRefreshing = false
let pendingRequests: Array<(token: string) => void> = []

client.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data.code !== 0) {
      // Token expired - try refresh
      if (data.code === 40101) {
        const refreshToken = localStorage.getItem('refresh_token')
        if (refreshToken && !isRefreshing) {
          isRefreshing = true
          return axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
            .then((res) => {
              const newData = res.data
              if (newData.code === 0 && newData.data) {
                localStorage.setItem('access_token', newData.data.access_token)
                localStorage.setItem('refresh_token', newData.data.refresh_token)
                pendingRequests.forEach((cb) => cb(newData.data.access_token))
                pendingRequests = []
                // Retry original request
                response.config.headers.Authorization = `Bearer ${newData.data.access_token}`
                return client(response.config)
              }
              throw new Error('refresh failed')
            })
            .catch(() => {
              clearAuthAndRedirect()
              return Promise.reject(new Error('登录已过期'))
            })
            .finally(() => { isRefreshing = false })
        } else if (isRefreshing) {
          // Queue the request while refreshing
          return new Promise((resolve) => {
            pendingRequests.push((token: string) => {
              response.config.headers.Authorization = `Bearer ${token}`
              resolve(client(response.config))
            })
          })
        }
      }

      if (data.code === 40100 && !response.config.url?.includes('/auth/login')) {
        clearAuthAndRedirect()
      }

      // Pass through gate_check_failed with data for custom handling
      if (data.code === 42201) {
        const err = new Error(data.message) as Error & { gateData: unknown }
        err.gateData = data.data
        return Promise.reject(err)
      }

      message.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message))
    }
    return data
  },
  (error) => {
    const data = error.response?.data
    const code = data?.code

    // Handle business error codes from non-200 responses
    if (code === 40101) {
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken && !isRefreshing) {
        isRefreshing = true
        return axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
          .then((res) => {
            const newData = res.data
            if (newData.code === 0 && newData.data) {
              localStorage.setItem('access_token', newData.data.access_token)
              localStorage.setItem('refresh_token', newData.data.refresh_token)
              pendingRequests.forEach((cb) => cb(newData.data.access_token))
              pendingRequests = []
              error.config.headers.Authorization = `Bearer ${newData.data.access_token}`
              return client(error.config)
            }
            throw new Error('refresh failed')
          })
          .catch(() => {
            clearAuthAndRedirect()
            return Promise.reject(new Error('登录已过期'))
          })
          .finally(() => { isRefreshing = false })
      } else if (isRefreshing) {
        return new Promise((resolve) => {
          pendingRequests.push((token: string) => {
            error.config.headers.Authorization = `Bearer ${token}`
            resolve(client(error.config))
          })
        })
      }
    }

    if ((code === 40100 || error.response?.status === 401) && !error.config?.url?.includes('/auth/login')) {
      clearAuthAndRedirect()
    }

    if (code === 42201) {
      const err = new Error(data.message) as Error & { gateData: unknown }
      err.gateData = data.data
      return Promise.reject(err)
    }

    message.error(data?.message || '网络异常')
    return Promise.reject(error)
  },
)

// Wrap client.get with request deduplication
const originalGet = client.get.bind(client)
client.get = function dedupGet(url: string, config?: any) {
  const key = `${url}|${JSON.stringify(config?.params || {})}`
  const inflight = inflightRequests.get(key)
  if (inflight) return inflight as any

  const promise = originalGet(url, config).finally(() => {
    inflightRequests.delete(key)
  })
  inflightRequests.set(key, promise)
  return promise
} as typeof client.get

export default client
