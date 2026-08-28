import type { RouteObject } from 'react-router-dom'
import type { ComponentType, LazyExoticComponent, ReactNode } from 'react'
import { MOBILE_FORM_MODULES, mobileFormModuleRouteSegment } from '@/config/mobileFormModules'

type GuardProps = { permission: string | string[]; children: ReactNode }

type FormModulePageProps = {
  templateCode: string
  title: string
  basePath: string
  dashboardPath?: string
  legacySchemeList?: boolean
}

type FormModuleFillPageProps = {
  templateCode: string
  listPath: string
  title: string
}

/** 移动端 FormModule 路由（与 PC 一一对应，basePath 带 /m 前缀） */
export function buildMobileFormModuleRoutes(deps: {
  Guard: ComponentType<GuardProps>
  FormModulePage: LazyExoticComponent<ComponentType<FormModulePageProps>>
  FormModuleFillPage: LazyExoticComponent<ComponentType<FormModuleFillPageProps>>
  Lazy: ComponentType<{ children: ReactNode }>
}): RouteObject[] {
  const { Guard, FormModulePage, FormModuleFillPage, Lazy } = deps
  const routes: RouteObject[] = []
  for (const mod of MOBILE_FORM_MODULES) {
    const seg = mobileFormModuleRouteSegment(mod.basePath)
    const mBase = `/m${mod.basePath}`
    routes.push({
      path: seg,
      element: (
        <Guard permission="form_data:view">
          <Lazy>
            <FormModulePage
              templateCode={mod.templateCode}
              title={mod.title}
              basePath={mBase}
              dashboardPath={mod.dashboardPath}
              legacySchemeList={mod.legacySchemeList}
            />
          </Lazy>
        </Guard>
      ),
    })
    routes.push({
      path: `${seg}/fill`,
      element: (
        <Guard permission="form_data:create">
          <Lazy>
            <FormModuleFillPage
              templateCode={mod.templateCode}
              listPath={mBase}
              title={mod.title}
            />
          </Lazy>
        </Guard>
      ),
    })
  }
  return routes
}
