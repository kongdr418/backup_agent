import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { getUserId } from '@/composables/useUserId'

const client = axios.create({
  baseURL: '',
  timeout: 60_000,
})

client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const uid = getUserId()
  const method = (config.method || 'get').toLowerCase()
  if (method === 'get' || method === 'delete' || method === 'head' || method === 'options') {
    // 无 body 的请求走 query param
    config.params = { ...config.params, user_id: uid }
  } else if (config.data && typeof config.data === 'object' && !(config.data instanceof FormData)) {
    config.data = { ...config.data, user_id: uid }
  } else if (config.data instanceof FormData) {
    // multipart 也得带 user_id,否则后端只能拿到 'anonymous'
    config.data.append('user_id', uid)
  }
  // FormData 必须由浏览器自动生成 multipart 边界,不能保留 application/json 默认
  if (config.data instanceof FormData && config.headers) {
    delete (config.headers as Record<string, unknown>)['Content-Type']
    delete (config.headers as Record<string, unknown>)['content-type']
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
