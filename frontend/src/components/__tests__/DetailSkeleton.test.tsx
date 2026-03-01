import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import DetailSkeleton from '../DetailSkeleton'

describe('DetailSkeleton', () => {
  it('renders without crashing', () => {
    const { container } = render(<DetailSkeleton />)
    expect(container.firstChild).toBeTruthy()
  })

  it('renders skeleton elements', () => {
    const { container } = render(<DetailSkeleton />)
    // Ant Design Skeleton renders with ant-skeleton class
    const skeletons = container.querySelectorAll('.ant-skeleton')
    expect(skeletons.length).toBeGreaterThanOrEqual(1)
  })

  it('has correct layout structure', () => {
    const { container } = render(<DetailSkeleton />)
    const wrapper = container.firstChild as HTMLElement
    expect(wrapper.className).toContain('space-y-6')
  })
})
