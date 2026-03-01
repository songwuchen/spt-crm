import { Skeleton } from 'antd'

export default function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Skeleton.Input active style={{ width: 200, height: 28 }} />
          <div className="mt-2">
            <Skeleton.Input active size="small" style={{ width: 300, height: 16 }} />
          </div>
        </div>
        <Skeleton.Button active style={{ width: 100 }} />
      </div>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <Skeleton active paragraph={{ rows: 4 }} />
      </div>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <Skeleton active paragraph={{ rows: 3 }} />
      </div>
    </div>
  )
}
