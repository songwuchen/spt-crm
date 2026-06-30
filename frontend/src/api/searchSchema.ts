import client from './client'

export type FieldType =
  | 'text' | 'number' | 'date' | 'datetime'
  | 'enum' | 'boolean' | 'relation' | 'people'

export interface SchemaFieldOption {
  value: string
  label: string
}

export interface SchemaField {
  key: string
  label: string
  type: FieldType
  operators: string[]
  sortable?: boolean
  options?: SchemaFieldOption[]
  optionSource?: string
}

export interface ResourceSchema {
  resource: string
  label: string
  fields: SchemaField[]
}

export interface FilterRule {
  field: string
  op: string
  value?: unknown
}

export interface FilterDsl {
  match: 'all' | 'any'
  rules: FilterRule[]
}

/** 拉取某资源的高级搜索字段定义（前端据此渲染条件构建器）。 */
export function getSearchSchema(resource: string) {
  return client.get(`/api/v1/search-schema/${resource}`) as unknown as Promise<{ data: ResourceSchema }>
}
