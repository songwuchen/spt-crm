/**
 * Download a file from an API endpoint (with JWT auth).
 */
export function downloadFile(url: string, filename: string) {
  const token = localStorage.getItem('access_token')
  const xhr = new XMLHttpRequest()
  xhr.open('GET', url, true)
  xhr.responseType = 'blob'
  if (token) {
    xhr.setRequestHeader('Authorization', `Bearer ${token}`)
  }
  xhr.onload = () => {
    if (xhr.status === 200) {
      const blob = xhr.response as Blob
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(a.href)
    }
  }
  xhr.send()
}
