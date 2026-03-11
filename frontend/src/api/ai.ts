import client from './client'
import type { ApiResponse, AiTaskItem, AiResultItem, AiPromptTemplateItem } from './types'

export const aiApi = {
  // Tasks
  listTasks: (params?: { biz_type?: string; biz_id?: string; status?: string }) =>
    client.get<unknown, ApiResponse<AiTaskItem[]>>('/api/v1/ai/tasks', { params }),
  createTask: (data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<AiTaskItem>>('/api/v1/ai/tasks', data),
  getTask: (id: string) =>
    client.get<unknown, ApiResponse<AiTaskItem>>(`/api/v1/ai/tasks/${id}`),
  updateTask: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<AiTaskItem>>(`/api/v1/ai/tasks/${id}`, data),

  // Results
  getResult: (taskId: string) =>
    client.get<unknown, ApiResponse<AiResultItem | null>>(`/api/v1/ai/results/${taskId}`),
  createResult: (data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<AiResultItem>>('/api/v1/ai/results', data),

  // Templates
  listTemplates: (taskType?: string) =>
    client.get<unknown, ApiResponse<AiPromptTemplateItem[]>>('/api/v1/ai/templates', { params: taskType ? { task_type: taskType } : {} }),
  createTemplate: (data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<AiPromptTemplateItem>>('/api/v1/ai/templates', data),
  updateTemplate: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<AiPromptTemplateItem>>(`/api/v1/ai/templates/${id}`, data),
  deleteTemplate: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/ai/templates/${id}`),

  // AI Analysis
  analyze: (data: { biz_type: string; biz_id: string; analysis_type: string }) =>
    client.post<unknown, ApiResponse<{ task_id: string; analysis_type: string; result: Record<string, unknown> }>>('/api/v1/ai/analyze', data),

  // Activity AI summary
  summarizeActivities: (bizType: string, bizId: string) =>
    client.post<unknown, ApiResponse<{ summary: string; key_points: string[]; suggestion: string }>>(
      `/api/v1/activities/ai-summary?biz_type=${bizType}&biz_id=${bizId}`
    ),

  // Similar projects
  findSimilarProjects: (projectId: string) =>
    client.post<unknown, ApiResponse<{ similar_projects: Array<{ name: string; similarity_score: number; reason: string }>; insights: string }>>(
      '/api/v1/ai/similar-projects', { project_id: projectId }
    ),

  // Knowledge Base
  listKnowledgeDocs: (params?: { doc_type?: string; keyword?: string; pageNo?: number; pageSize?: number }) =>
    client.get<unknown, ApiResponse<{ items: KnowledgeDoc[]; total: number }>>('/api/v1/ai/knowledge/documents', { params }),
  getKnowledgeDoc: (id: string) =>
    client.get<unknown, ApiResponse<KnowledgeDoc & { content_text: string }>>(`/api/v1/ai/knowledge/documents/${id}`),
  createKnowledgeDoc: (data: { title: string; doc_type: string; content_text: string; source_filename?: string; metadata_json?: Record<string, unknown> }) =>
    client.post<unknown, ApiResponse<KnowledgeDoc>>('/api/v1/ai/knowledge/documents', data),
  updateKnowledgeDoc: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<KnowledgeDoc>>(`/api/v1/ai/knowledge/documents/${id}`, data),
  deleteKnowledgeDoc: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/ai/knowledge/documents/${id}`),
  searchKnowledge: (data: { query: string; doc_type?: string; top_k?: number }) =>
    client.post<unknown, ApiResponse<KnowledgeSearchResult[]>>('/api/v1/ai/knowledge/search', data),
}

export interface KnowledgeDoc {
  id: string
  title: string
  doc_type: string
  source_filename?: string
  chunk_count: number
  status: string
  metadata_json?: Record<string, unknown>
  created_by_name?: string
  created_at: string
  updated_at: string
}

export interface KnowledgeSearchResult {
  chunk_id: string
  document_id: string
  doc_title: string
  chunk_index: number
  content: string
  score: number
}
