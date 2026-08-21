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
  // The Content-Type sent on the PUT must EXACTLY equal what the presigned URL was
  // signed with (OSS V1 signs Content-Type). Normalise once and use it for both.
  const contentType = file.type || 'application/octet-stream'
  const presign = await client.post<unknown, ApiResponse<PresignResult>>(
    '/api/v1/attachments/presign-upload',
    { filename: file.name, content_type: contentType, file_size: file.size, biz_type: bizType, biz_id: bizId },
  )
  const info = presign.data
  if (info?.mode !== 'direct' || !info.upload_url || !info.key) {
    return multipartUpload(file, bizType, bizId)
  }

  let putRes: Response
  try {
    putRes = await fetch(info.upload_url, {
      method: info.method || 'PUT',
      body: file,
      headers: { 'Content-Type': contentType },
    })
  } catch {
    // fetch threw before any response → preflight blocked or host unreachable = CORS/network
    throw new Error('CORS_OR_NETWORK')
  }
  if (!putRes.ok) {
    const detail = await putRes.text().catch(() => '')
    throw new Error(`直传被对象存储拒绝 (HTTP ${putRes.status})${detail ? '：' + detail.slice(0, 200) : ''}`)
  }

  return client.post<unknown, ApiResponse<{ id: string }>>('/api/v1/attachments/register', {
    key: info.key, original_name: file.name, content_type: contentType,
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

export type WebOfficeToken = {
  enabled: boolean
  reason?: 'unsupported' | 'not_configured' | 'not_oss'
  url?: string
  access_token?: string
  refresh_token?: string
}

async function getWebOfficeToken(id: string, noDownload = false): Promise<WebOfficeToken> {
  const res = await client.get<unknown, ApiResponse<WebOfficeToken>>(
    `/api/v1/attachments/${id}/weboffice`,
    { params: { no_download: noDownload ? 1 : 0 } },
  )
  return res.data
}

async function refreshWebOfficeToken(accessToken: string, refreshToken: string): Promise<WebOfficeToken> {
  const res = await client.post<unknown, ApiResponse<WebOfficeToken>>(
    '/api/v1/attachments/weboffice/refresh',
    { access_token: accessToken, refresh_token: refreshToken },
  )
  return res.data
}

export const attachmentApi = {
  upload,
  getUrl,
  getWebOfficeToken,
  refreshWebOfficeToken,
  delete: (id: string) => client.delete<unknown, ApiResponse<null>>(`/api/v1/attachments/${id}`),
  /** 将已直传的附件挂到业务单据（创建页 FileField → 保存后关联） */
  link: (attachmentIds: string[], bizType: string, bizId: string) =>
    client.post<unknown, ApiResponse<{ linked: number }>>('/api/v1/attachments/link', {
      attachment_ids: attachmentIds,
      biz_type: bizType,
      biz_id: bizId,
    }),
  /** 按 id 批量取元数据（低代码 file/image 只读表补全大小/上传人/时间） */
  listBatch: (ids: string[]) =>
    ids.length
      ? client.get<unknown, ApiResponse<Array<{
          id: string
          original_name: string
          content_type?: string
          file_size: number
          uploader_name?: string
          created_at: string
        }>>>('/api/v1/attachments/batch', { params: { ids: ids.join(',') } }).then((r) =>
          (r.data || []).map((a) => ({
            id: a.id,
            name: a.original_name,
            content_type: a.content_type,
            file_size: a.file_size,
            uploader_name: a.uploader_name,
            created_at: a.created_at,
          })),
        )
      : Promise.resolve([]),
}
