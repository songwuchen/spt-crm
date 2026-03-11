import { Dropdown, Button, Checkbox } from 'antd'
import { SettingOutlined } from '@ant-design/icons'

interface ColumnMeta {
  key: string
  title: string
}

interface Props {
  allColumnKeys: ColumnMeta[]
  hiddenKeys: string[]
  onChange: (hiddenKeys: string[]) => void
}

export default function ColumnConfigDropdown({ allColumnKeys, hiddenKeys, onChange }: Props) {
  return (
    <Dropdown trigger={['click']} dropdownRender={() => (
      <div className="bg-white rounded-lg border border-slate-200 shadow-lg p-3 min-w-[160px]">
        <div className="text-xs font-bold text-slate-400 uppercase mb-2">显示列</div>
        {allColumnKeys.map((c) => (
          <label key={c.key} className="flex items-center gap-2 py-1 cursor-pointer text-sm text-slate-700">
            <Checkbox
              checked={!hiddenKeys.includes(c.key)}
              onChange={(e) => {
                if (e.target.checked) {
                  onChange(hiddenKeys.filter((k) => k !== c.key))
                } else {
                  onChange([...hiddenKeys, c.key])
                }
              }}
            />
            {c.title}
          </label>
        ))}
      </div>
    )}>
      <Button icon={<SettingOutlined />} />
    </Dropdown>
  )
}
