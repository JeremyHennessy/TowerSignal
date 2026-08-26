import { useState } from 'react'

export function ShareButton({ url, label = 'Share link', className = '' }: { url?: string; label?: string; className?: string }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    const target = url ?? window.location.href
    try {
      await navigator.clipboard.writeText(target)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      const input = document.createElement('textarea')
      input.value = target
      input.setAttribute('readonly', '')
      input.style.position = 'fixed'
      input.style.opacity = '0'
      document.body.appendChild(input)
      input.select()
      document.execCommand('copy')
      document.body.removeChild(input)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    }
  }

  return <button className={`share-button ${className}`.trim()} onClick={() => void copy()}>{copied ? 'Link copied' : label}</button>
}
