import axios from 'axios'
import { message } from 'antd'
import { useAuthStore } from '@/stores/useAuthStore'

const client = axios.create({
  baseURL: '',
  timeout: 30000,
})

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
              useAuthStore.getState().logout()
              window.location.href = '/login'
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

      if (data.code === 40100) {
        useAuthStore.getState().logout()
        window.location.href = '/login'
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
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    message.error(error.response?.data?.message || '网络异常')
    return Promise.reject(error)
  },
)

export default client
