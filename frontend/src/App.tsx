import { RouterProvider } from 'react-router-dom'
import { router } from './router'
import { PdfPreviewHost } from '@/components/PdfPreviewModal'

export default function App() {
  return (
    <>
      <RouterProvider router={router} />
      <PdfPreviewHost />
    </>
  )
}
