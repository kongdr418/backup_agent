import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { getUserId } from '@/composables/useUserId'

const client = axios.create({
  baseURL: '',
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json; charset=utf-8' },
})

client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const uid = getUserId()
  const method = (config.method || 'get').toLowerCase()
  if (method === 'get' || method === 'delete' || method === 'head' || method === 'options') {
    // 无 body 的请求走 query param
    config.params = { ...config.params, user_id: uid }
  } else if (config.data && typeof config.data === 'object' && !(config.data instanceof FormData)) {
    config.data = { ...config.data, user_id: uid }
  }
  return config
})

client.interceptors.response.use(
  (res) => res,
  (err: AxiosError<{ error?: string }>) => {
    const msg = err.response?.data?.error || err.message || '请求失败'
    return Promise.reject(new Error(msg))
  },
)

export default client
