import client from './client'
import type { ApiResponse } from './types'

export const attachmentApi = {
  upload: (file: File, bizType?: string, bizId?: string) => {
    const formData = new FormData()
    formData.append('file', file)
    if (bizType) formData.append('biz_type', bizType)
    if (bizId) formData.append('biz_id', bizId)
    return client.post<unknown, ApiResponse<{ id: string; original_name: string }>>('/api/v1/attachments', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  downloadUrl: (id: string) => `/api/v1/attachments/${id}/download`,
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<null>>(`/api/v1/attachments/${id}`),
}
