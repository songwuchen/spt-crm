/**
 * Download a file from an API endpoint (with JWT auth).
 * Rejects on non-200 so调用方可提示失败。
 */
export function downloadFile(url: string, filename: string): Promise<void> {
  const token = localStorage.getItem('access_token')
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('GET', url, true)
    xhr.responseType = 'blob'
    if (token) {
      xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    }

    const failFromBlob = (blob: Blob, fallback: string) => {
      blob.text().then((t) => {
        try {
          const j = JSON.parse(t) as { message?: string }
          reject(new Error(j.message || fallback))
        } catch {
          reject(new Error(fallback))
        }
      }).catch(() => reject(new Error(fallback)))
    }

    xhr.onload = () => {
      const blob = xhr.response as Blob
      const ctype = (xhr.getResponseHeader('Content-Type') || '').toLowerCase()
      if (xhr.status === 200) {
        // 后端错误有时仍 200 JSON；Excel 一般为 octet-stream / spreadsheet
        if (ctype.includes('application/json')) {
          failFromBlob(blob, '导出失败')
          return
        }
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = filename
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(a.href)
        resolve()
        return
      }
      if (ctype.includes('application/json')) {
        failFromBlob(blob, `导出失败（${xhr.status}）`)
        return
      }
      reject(new Error(`导出失败（${xhr.status}）`))
    }
    xhr.onerror = () => reject(new Error('网络错误，导出失败'))
    xhr.send()
  })
}
