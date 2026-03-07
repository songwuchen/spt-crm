import client from './client'

export const productApi = {
  list: (params?: Record<string, unknown>) => client.get('/api/v1/products', { params }),
  get: (id: string) => client.get(`/api/v1/products/${id}`),
  create: (data: Record<string, unknown>) => client.post('/api/v1/products', data),
  update: (id: string, data: Record<string, unknown>) => client.put(`/api/v1/products/${id}`, data),
  delete: (id: string) => client.delete(`/api/v1/products/${id}`),

  listCategories: () => client.get('/api/v1/products/categories'),
  createCategory: (data: Record<string, unknown>) => client.post('/api/v1/products/categories', data),
  updateCategory: (id: string, data: Record<string, unknown>) => client.put(`/api/v1/products/categories/${id}`, data),
  deleteCategory: (id: string) => client.delete(`/api/v1/products/categories/${id}`),
  checkUnique: (productCode: string, excludeId?: string) =>
    client.get('/api/v1/products/check-unique', {
      params: { product_code: productCode, ...(excludeId ? { exclude_id: excludeId } : {}) },
    }),
}
