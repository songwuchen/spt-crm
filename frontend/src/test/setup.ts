import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Mock window.matchMedia (required by Ant Design)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock window.getComputedStyle (required by Ant Design)
const originalGetComputedStyle = window.getComputedStyle
window.getComputedStyle = (elt: Element, pseudoElt?: string | null) => {
  try {
    return originalGetComputedStyle(elt, pseudoElt)
  } catch {
    return {} as CSSStyleDeclaration
  }
}

// Mock ResizeObserver
class ResizeObserverMock {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
}
window.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver

// Mock scrollTo
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo
Element.prototype.scrollTo = vi.fn() as unknown as typeof Element.prototype.scrollTo

// Mock react-router-dom
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({}),
  }
})

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { store = {} },
    get length() { return Object.keys(store).length },
    key: (i: number) => Object.keys(store)[i] ?? null,
  }
})()
Object.defineProperty(window, 'localStorage', { value: localStorageMock })
