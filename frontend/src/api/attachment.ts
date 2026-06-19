import client from './client'
import type { ApiResponse } from './types'

interface PresignResult {
  mode: 'direct' | 'multipart'
  storage_backend?: string
  key?: string
  upload_url?: string
  method?: string
}

async function multipartUpload(file: File, bizType?: string, bizId?: string) {
  const formData = new FormData()
  formData.append('file', file)
  if (bizType) formData.append('biz_type', bizType)
  if (bizId) formData.append('biz_id', bizId)
  return client.post<unknown, ApiResponse<{ id: string }>>('/api/v1/attachments', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/**
 * Upload a file. When the active backend is object storage the browser uploads
 * directly (直传) to OSS/MinIO via a presigned PUT URL, then registers metadata;
 * otherwise it falls back to a server-side multipart upload.
 */
async function upload(file: File, bizType?: string, bizId?: string) {
  const presign = await client.post<unknown, ApiResponse<PresignResult>>(
    '/api/v1/attachments/presign-upload',
    { filename: file.name, content_type: file.type || undefined, file_size: file.size, biz_type: bizType, biz_id: bizId },
  )
  const info = presign.data
  if (info?.mode !== 'direct' || !info.upload_url || !info.key) {
    return multipartUpload(file, bizType, bizId)
  }

  const putRes = await fetch(info.upload_url, {
    method: info.method || 'PUT',
    body: file,
    headers: file.type ? { 'Content-Type': file.type } : undefined,
  })
  if (!putRes.ok) throw new Error(`直传失败 (${putRes.status})`)

  return client.post<unknown, ApiResponse<{ id: string }>>('/api/v1/attachments/register', {
    key: info.key, original_name: file.name, content_type: file.type || undefined,
    biz_type: bizType, biz_id: bizId,
  })
}

/** Resolve a directly-usable URL for preview (download=false) or download (download=true). */
async function getUrl(id: string, download = false): Promise<string> {
  const res = await client.get<unknown, ApiResponse<{ url: string }>>(
    `/api/v1/attachments/${id}/url`, { params: { download: download ? 1 : 0 } },
  )
  return res.data.url
}

export const attachmentApi = {
  upload,
  getUrl,
  delete: (id: string) => client.delete<unknown, ApiResponse<null>>(`/api/v1/attachments/${id}`),
}
