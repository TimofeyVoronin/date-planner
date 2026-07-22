export async function copyTextWithFallback(value: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value)
      return true
    }
    catch {
      // Some browsers deny Clipboard API access outside a secure context.
    }
  }

  const textArea = document.createElement('textarea')
  textArea.value = value
  textArea.readOnly = true
  textArea.style.position = 'fixed'
  textArea.style.opacity = '0'
  document.body.append(textArea)
  textArea.select()

  try {
    return document.execCommand('copy')
  }
  finally {
    textArea.remove()
  }
}
