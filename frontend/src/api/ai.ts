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
}
