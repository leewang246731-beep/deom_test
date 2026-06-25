/** SSE streaming client for KB Q&A */
export function streamKBAsk(question, conversationId, token, callbacks) {
  const { onContext, onToken, onDone, onError } = callbacks
  const controller = new AbortController()

  fetch('/api/v1/kb/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ question, conversation_id: conversationId }),
    signal: controller.signal,
  }).then(async response => {
    if (!response.ok) {
      const text = await response.text()
      onError?.(new Error(text))
      return
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'context') onContext?.(data)
            else if (data.type === 'token') onToken?.(data.content)
            else if (data.type === 'done') onDone?.(data)
            else if (data.type === 'error') onError?.(new Error(data.msg))
            else if (data.type === 'warning') onContext?.({ sources: [], warning: data.msg })
          } catch { /* skip bad lines */ }
        }
      }
    }
  }).catch(e => {
    if (e.name !== 'AbortError') onError?.(e)
  })

  return controller
}
