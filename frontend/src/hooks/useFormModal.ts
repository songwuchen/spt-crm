import { useState, useCallback } from 'react'

interface FormModalState<T> {
  open: boolean
  editingId: string | null
  formData: T
}

export function useFormModal<T extends Record<string, unknown>>(defaultForm: T) {
  const [state, setState] = useState<FormModalState<T>>({
    open: false,
    editingId: null,
    formData: { ...defaultForm },
  })

  const openCreate = useCallback(() => {
    setState({ open: true, editingId: null, formData: { ...defaultForm } })
  }, [defaultForm])

  const openEdit = useCallback((id: string, data: Partial<T>) => {
    setState({ open: true, editingId: id, formData: { ...defaultForm, ...data } })
  }, [defaultForm])

  const close = useCallback(() => {
    setState(s => ({ ...s, open: false, editingId: null }))
  }, [])

  const setField = useCallback(<K extends keyof T>(key: K, value: T[K]) => {
    setState(s => ({ ...s, formData: { ...s.formData, [key]: value } }))
  }, [])

  const setFormData = useCallback((data: Partial<T>) => {
    setState(s => ({ ...s, formData: { ...s.formData, ...data } }))
  }, [])

  return {
    open: state.open,
    editingId: state.editingId,
    isEditing: state.editingId !== null,
    formData: state.formData,
    openCreate,
    openEdit,
    close,
    setField,
    setFormData,
  }
}
