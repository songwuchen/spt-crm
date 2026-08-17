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
    xhr.onload = () => {
      if (xhr.status === 200) {
        const blob = xhr.response as Blob
        // 后端错误有时仍 200 JSON；Excel 一般为 octet-stream / spreadsheet
        const ctype = (xhr.getResponseHeader('Content-Type') || '').toLowerCase()
        if (ctype.includes('application/json')) {
          blob.text().then((t) => {
            try {
              const j = JSON.parse(t) as { message?: string }
              reject(new Error(j.message || '导出失败'))
            } catch {
              reject(new Error('导出失败'))
            }
          }).catch(() => reject(new Error('导出失败')))
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
      reject(new Error(`导出失败（${xhr.status}）`))
    }
    xhr.onerror = () => reject(new Error('网络错误，导出失败'))
    xhr.send()
  })
}
