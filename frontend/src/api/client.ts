import axios, { type AxiosError } from 'axios'

const client = axios.create({
  baseURL: '',
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json; charset=utf-8' },
})

client.interceptors.response.use(
  (res) => res,
  (err: AxiosError<{ error?: string }>) => {
    const msg = err.response?.data?.error || err.message || '请求失败'
    return Promise.reject(new Error(msg))
  },
)

export default client
