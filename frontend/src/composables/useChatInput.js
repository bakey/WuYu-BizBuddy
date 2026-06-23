// 让「追问」按钮能聚焦到输入框：ChatInputBar 挂载时注册 focus 回调，
// ChatMessage 的追问按钮调用 focusInput() 触发。
let _focusFn = null

export function useChatInput() {
  function registerFocus(fn) {
    _focusFn = fn
  }
  function focusInput() {
    if (_focusFn) _focusFn()
  }
  return { registerFocus, focusInput }
}
