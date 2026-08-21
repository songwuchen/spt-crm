/** 表单设计器：人员/部门字段「可选范围」（对齐简道云：系统范围 / 指定角色 / 指定部门）。 */
import { useEffect, useMemo, useState } from 'react'
import { Select, Switch, TreeSelect, Typography } from 'antd'
import { TeamOutlined, ApartmentOutlined } from '@ant-design/icons'
import client from '@/api/client'
import type { ApiResponse, Department } from '@/api/types'
import { lowcodeApi } from '@/api/lowcode'
import type { PickableScope } from '@/components/lowcode/fields/PersonField'

const { Text } = Typography

type Mode = 'all' | 'scope' | 'roles' | 'depts'

type TreeNode = { title: string; value: string; children?: TreeNode[] }

function detectMode(scope?: PickableScope | null): Mode {
  if (!scope) return 'all'
  if (scope.scope_code) return 'scope'
  // 用键判断模式，允许暂时为空（刚切到「指定角色/部门」）
  if ('role_codes' in scope) return 'roles'
  if ('dept_ids' in scope) return 'depts'
  return 'all'
}

function buildDeptTree(nodes: Department[]): TreeNode[] {
  return (nodes || []).map((n) => ({
    title: n.name,
    value: n.id,
    children: n.children?.length ? buildDeptTree(n.children) : undefined,
  }))
}

function RoleMultiSelect({
  value,
  onChange,
}: {
  value: string[]
  onChange: (codes: string[]) => void
}) {
  const [opts, setOpts] = useState<{ value: string; label: string; name: string; member_count: number }[]>([])

  useEffect(() => {
    lowcodeApi.pickableRoles({ codes: value.join(',') || undefined }).then((r) => {
      const list = Array.isArray(r.data) ? r.data : []
      setOpts(list.map((role) => ({
        value: role.code,
        name: role.name || role.code,
        member_count: role.member_count ?? 0,
        label: `${role.name || role.code}${typeof role.member_count === 'number' ? `（${role.member_count}人）` : ''}`,
      })))
    }).catch(() => setOpts([]))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const options = useMemo(() => {
    const next = [...opts]
    for (const code of value) {
      if (!next.some((o) => o.value === code)) {
        next.unshift({ value: code, name: code, member_count: 0, label: code })
      }
    }
    return next
  }, [opts, value])

  return (
    <Select
      size="small"
      mode="multiple"
      allowClear
      style={{ width: '100%', marginTop: 4 }}
      placeholder="选择角色"
      value={value}
      options={options}
      optionFilterProp="label"
      showSearch
      optionRender={(opt) => (
        <div className="flex items-center gap-2 py-0.5">
          <TeamOutlined className="text-blue-500" />
          <div className="min-w-0 flex-1">
            <div className="truncate text-slate-800">{String(opt.data?.name || opt.label)}</div>
            <div className="text-xs text-slate-400 truncate">
              {String(opt.value)}
              {typeof opt.data?.member_count === 'number' ? ` · ${opt.data.member_count} 人` : ''}
            </div>
          </div>
        </div>
      )}
      tagRender={({ value: code, closable, onClose }) => {
        const opt = options.find((o) => o.value === code)
        return (
          <span className="ant-select-selection-item inline-flex items-center gap-1 !me-1 !ps-1.5">
            <TeamOutlined className="text-blue-500 text-xs" />
            <span className="max-w-[140px] truncate">{opt?.name || String(code)}</span>
            {closable ? (
              <span className="ant-select-selection-item-remove cursor-pointer" onClick={onClose}>×</span>
            ) : null}
          </span>
        )
      }}
      onChange={(codes) => onChange(codes.map(String))}
    />
  )
}

function DeptMultiSelect({
  value,
  onChange,
}: {
  value: string[]
  onChange: (ids: string[]) => void
}) {
  const [tree, setTree] = useState<TreeNode[]>([])

  useEffect(() => {
    client.get<unknown, ApiResponse<Department[]>>('/api/v1/lc/pickable-departments')
      .then((r) => setTree(buildDeptTree((r.data as Department[]) || [])))
      .catch(() => setTree([]))
  }, [])

  return (
    <TreeSelect
      size="small"
      treeCheckable
      showCheckedStrategy={TreeSelect.SHOW_PARENT}
      allowClear
      treeDefaultExpandAll={false}
      style={{ width: '100%', marginTop: 4 }}
      placeholder="选择部门"
      treeData={tree}
      value={value}
      onChange={(ids) => onChange((ids as string[]).map(String))}
      maxTagCount="responsive"
      showSearch
      treeNodeFilterProp="title"
      tagRender={({ label, closable, onClose }) => (
        <span className="ant-select-selection-item inline-flex items-center gap-1 !me-1 !ps-1.5">
          <ApartmentOutlined className="text-emerald-600 text-xs" />
          <span className="max-w-[140px] truncate">{label}</span>
          {closable ? (
            <span className="ant-select-selection-item-remove cursor-pointer" onClick={onClose}>×</span>
          ) : null}
        </span>
      )}
    />
  )
}

export default function PickableScopePropsEditor({
  kind,
  value,
  scopeOptions,
  onChange,
  showDeptFilterSwitch,
}: {
  kind: 'person' | 'department'
  value?: PickableScope | null
  scopeOptions: { label: string; value: string }[]
  onChange: (next: PickableScope | undefined) => void
  /** 人员字段：是否显示「按科室再收窄」 */
  showDeptFilterSwitch?: boolean
}) {
  const mode = detectMode(value)
  const filterOn = !!value?.filter_by_fields?.length

  const setMode = (m: Mode) => {
    if (m === 'all') {
      onChange(undefined)
      return
    }
    if (m === 'scope') {
      onChange({
        scope_code: value?.scope_code || scopeOptions[0]?.value,
        ...(filterOn && kind === 'person' ? { filter_by_fields: ['offices', 'offices_multi'] } : {}),
      })
      return
    }
    if (m === 'roles') {
      onChange({
        role_codes: value?.role_codes?.length ? value.role_codes : [],
        ...(filterOn ? { filter_by_fields: ['offices', 'offices_multi'] } : {}),
      })
      return
    }
    onChange({
      dept_ids: value?.dept_ids?.length ? value.dept_ids : [],
      include_children: value?.include_children !== false,
      ...(filterOn && kind === 'person' ? { filter_by_fields: ['offices', 'offices_multi'] } : {}),
    })
  }

  const modeOptions = kind === 'person'
    ? [
        { value: 'all', label: '全部人员' },
        { value: 'scope', label: '系统可选范围' },
        { value: 'roles', label: '指定角色' },
        { value: 'depts', label: '指定部门' },
      ]
    : [
        { value: 'all', label: '全部部门' },
        { value: 'scope', label: '系统可选范围' },
        { value: 'depts', label: '指定部门' },
      ]

  return (
    <div>
      <Text type="secondary" style={{ fontSize: 12 }}>
        {kind === 'person' ? '可选人员范围' : '可选部门范围'}
      </Text>
      <Select
        size="small"
        style={{ width: '100%', marginTop: 4 }}
        value={mode}
        options={modeOptions}
        onChange={(m) => setMode(m as Mode)}
      />

      {mode === 'scope' && (
        <Select
          allowClear
          size="small"
          style={{ width: '100%', marginTop: 8 }}
          placeholder="选择系统可选范围"
          options={scopeOptions}
          value={value?.scope_code || undefined}
          onChange={(code) => {
            if (!code) {
              onChange(undefined)
              return
            }
            onChange({
              scope_code: code,
              ...(filterOn && kind === 'person' ? { filter_by_fields: ['offices', 'offices_multi'] } : {}),
            })
          }}
        />
      )}

      {mode === 'roles' && kind === 'person' && (
        <RoleMultiSelect
          value={value?.role_codes || []}
          onChange={(codes) => {
            onChange({
              role_codes: codes,
              ...(filterOn ? { filter_by_fields: ['offices', 'offices_multi'] } : {}),
            })
          }}
        />
      )}

      {mode === 'depts' && (
        <>
          <DeptMultiSelect
            value={value?.dept_ids || []}
            onChange={(ids) => {
              onChange({
                dept_ids: ids,
                include_children: value?.include_children !== false,
                ...(filterOn && kind === 'person' ? { filter_by_fields: ['offices', 'offices_multi'] } : {}),
              })
            }}
          />
          <div style={{ marginTop: 8 }}>
            <Switch
              size="small"
              checked={value?.include_children !== false}
              onChange={(on) => {
                onChange({
                  dept_ids: value?.dept_ids || [],
                  include_children: on,
                  ...(filterOn && kind === 'person' ? { filter_by_fields: ['offices', 'offices_multi'] } : {}),
                })
              }}
            />
            <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>含下级部门</Text>
          </div>
        </>
      )}

      {showDeptFilterSwitch && kind === 'person' && mode !== 'all' && (
        <div style={{ marginTop: 8 }}>
          <Switch
            size="small"
            checked={filterOn}
            onChange={(on) => {
              const base: PickableScope =
                mode === 'scope'
                  ? { scope_code: value?.scope_code }
                  : mode === 'roles'
                    ? { role_codes: value?.role_codes || [] }
                    : {
                        dept_ids: value?.dept_ids || [],
                        include_children: value?.include_children !== false,
                      }
              if (on) base.filter_by_fields = ['offices', 'offices_multi']
              onChange(base)
            }}
          />
          <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>按同单「科室」字段再收窄</Text>
        </div>
      )}

      <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
        {mode === 'scope'
          ? '范围在「系统管理 → 可选范围」维护。'
          : mode === 'roles'
            ? '仅可选中角色的成员。'
            : mode === 'depts'
              ? (kind === 'person' ? '仅可选指定部门（及下级）内的成员。' : '仅可选指定部门（及下级）。')
              : '不限制可选范围。'}
      </Text>
    </div>
  )
}
