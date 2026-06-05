export function shouldSubmitDiscussionOnEnter(input: {
  key: string
  shiftKey?: boolean
  isComposing?: boolean
}) {
  return input.key === 'Enter' && !input.shiftKey && !input.isComposing
}
