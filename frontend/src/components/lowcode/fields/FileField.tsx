// 附件/图片字段(file / image)。值为 [{id, name}] 数组;上传走 attachmentApi(本地/OSS/MinIO 可插拔)。
import { useEffect, useState } from 'react'
import { Upload, Button, message, Space } from 'antd'
import type { UploadFile } from 'antd'
import { UploadOutlined, PaperClipOutlined } from '@ant-design/icons'
import { attachmentApi } from '@/api/attachment'

interface Att { id: string; name: string }

export default function FileField({
  value, onChange, image, readonly,
}: {
  value: unknown
  onChange: (v: unknown) => void
  image?: boolean
  readonly?: boolean
}) {
  const atts: Att[] = Array.isArray(value) ? (value as Att[]) : []
  const [urls, setUrls] = useState<Record<string, string>>({})

  // 图片: 解析缩略图 URL(异步,按 id 缓存)
  useEffect(() => {
    if (!image) return
    let alive = true
    ;(async () => {
      const next: Record<string, string> = {}
      for (const a of atts) {
        if (urls[a.id]) { next[a.id] = urls[a.id]; continue }
        try { next[a.id] = await attachmentApi.getUrl(a.id, false) } catch { /* ignore */ }
      }
      if (alive) setUrls(next)
    })()
    return () => { alive = false }
  }, [image, JSON.stringify(atts.map((a) => a.id))])  // eslint-disable-line react-hooks/exhaustive-deps

  const openFile = async (id: string, download = false) => {
    try { const u = await attachmentApi.getUrl(id, download); window.open(u, '_blank') } catch { message.error('获取文件地址失败') }
  }

  if (readonly) {
    if (!atts.length) return <div style={{ paddingTop: 4 }}>—</div>
    if (image) {
      return (
        <Space wrap style={{ paddingTop: 4 }}>
          {atts.map((a) => (
            <img key={a.id} src={urls[a.id]} alt={a.name} style={{ width: 72, height: 72, objectFit: 'cover', borderRadius: 4, cursor: 'pointer' }}
              onClick={() => openFile(a.id)} />
          ))}
        </Space>
      )
    }
    return (
      <div style={{ paddingTop: 4 }}>
        {atts.map((a) => (
          <div key={a.id}>
            <a onClick={() => openFile(a.id, true)}><PaperClipOutlined /> {a.name}</a>
          </div>
        ))}
      </div>
    )
  }

  const fileList: UploadFile[] = atts.map((a) => ({
    uid: a.id, name: a.name, status: 'done',
    url: image ? urls[a.id] : undefined,
  }))

  const customRequest = async (opt: { file: unknown; onSuccess?: (b: unknown) => void; onError?: (e: Error) => void }) => {
    const file = opt.file as File
    try {
      const res = await attachmentApi.upload(file)
      onChange([...atts, { id: res.data.id, name: file.name }])
      opt.onSuccess?.({})
    } catch (e) {
      message.error('上传失败: ' + (e as Error).message)
      opt.onError?.(e as Error)
    }
  }

  const onRemove = (f: UploadFile) => {
    onChange(atts.filter((a) => a.id !== f.uid))
    return true
  }

  return (
    <Upload
      listType={image ? 'picture-card' : 'text'}
      fileList={fileList}
      customRequest={customRequest as never}
      onRemove={onRemove}
      onPreview={(f) => openFile(String(f.uid))}
      accept={image ? 'image/*' : undefined}
    >
      {image
        ? <div><UploadOutlined /><div style={{ marginTop: 4 }}>上传</div></div>
        : <Button icon={<UploadOutlined />}>上传附件</Button>}
    </Upload>
  )
}
