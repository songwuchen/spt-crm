/** Normalize low-code file/image field values for display.
 *  Real uploads: { id, name }. JDY import may be name strings or { name } only.
 */
export type FileFieldAtt = { id: string; name: string; metaOnly?: boolean }

const META_PREFIX = 'jdy-meta:'

export function isMetaOnlyAttachmentId(id: string | undefined | null): boolean {
  return !!id && id.startsWith(META_PREFIX)
}

export function normalizeFileFieldValue(value: unknown): FileFieldAtt[] {
  if (!Array.isArray(value)) return []
  const out: FileFieldAtt[] = []
  for (const item of value) {
    if (typeof item === 'string') {
      const name = item.trim()
      if (!name) continue
      out.push({ id: `${META_PREFIX}${name}`, name, metaOnly: true })
      continue
    }
    if (!item || typeof item !== 'object') continue
    const o = item as Record<string, unknown>
    const name = String(o.name ?? o.fileName ?? o.filename ?? '').trim()
    const id = String(o.id ?? '').trim()
    if (id && name) {
      out.push({
        id,
        name,
        metaOnly: isMetaOnlyAttachmentId(id) || o.metaOnly === true,
      })
    } else if (name) {
      out.push({ id: `${META_PREFIX}${name}`, name, metaOnly: true })
    } else if (id) {
      out.push({
        id,
        name: id,
        metaOnly: isMetaOnlyAttachmentId(id),
      })
    }
  }
  return out
}
