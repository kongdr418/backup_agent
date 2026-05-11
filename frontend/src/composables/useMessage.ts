import { useMessage } from 'naive-ui'

/**
 * Thin wrapper exposing naive-ui message API for non-component contexts.
 * Use within `setup()` only — naive-ui requires a provider in App.vue.
 */
export function useToast() {
  const message = useMessage()
  return {
    success: (text: string) => message.success(text),
    info: (text: string) => message.info(text),
    warning: (text: string) => message.warning(text),
    error: (text: string) => message.error(text),
  }
}
