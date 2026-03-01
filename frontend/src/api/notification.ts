import client from './client'
import type { ApiResponse } from './types'

export interface NotificationItem {
  id: string
  type: string
  title: string
  content?: string
  biz_type?: string
  biz_id?: string
  sender_name?: string
  is_read: boolean
  extra_json?: Record<string, unknown>
  created_at: string
}

export const notificationApi = {
  list: (unread_only = false) =>
    client.get<unknown, ApiResponse<NotificationItem[]>>('/api/v1/notifications', { params: { unread_only } }),
  unreadCount: () =>
    client.get<unknown, ApiResponse<{ count: number }>>('/api/v1/notifications/unread_count'),
  markRead: (ids: string[]) =>
    client.post<unknown, ApiResponse<void>>('/api/v1/notifications/mark_read', { ids }),
  markAllRead: () =>
    client.post<unknown, ApiResponse<void>>('/api/v1/notifications/mark_all_read'),
}
