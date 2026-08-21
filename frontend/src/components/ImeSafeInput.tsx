/** 对 IME 友好的受控输入：组字期间不回写父级 value，避免打断中文输入。 */
import { forwardRef, useEffect, useRef, useState, type ChangeEvent, type CompositionEvent } from 'react'
import { Input } from 'antd'
import type { InputProps, InputRef } from 'antd'

const ImeSafeInput = forwardRef<InputRef, InputProps>(function ImeSafeInput(
  { value, onChange, onCompositionStart, onCompositionEnd, ...rest },
  ref,
) {
  const composingRef = useRef(false)
  const [inner, setInner] = useState(() => (value == null ? '' : String(value)))

  useEffect(() => {
    if (composingRef.current) return
    setInner(value == null ? '' : String(value))
  }, [value])

  return (
    <Input
      {...rest}
      ref={ref}
      value={inner}
      onChange={(e) => {
        setInner(e.target.value)
        if (!composingRef.current) onChange?.(e)
      }}
      onCompositionStart={(e: CompositionEvent<HTMLInputElement>) => {
        composingRef.current = true
        onCompositionStart?.(e)
      }}
      onCompositionEnd={(e: CompositionEvent<HTMLInputElement>) => {
        composingRef.current = false
        const next = e.currentTarget.value
        setInner(next)
        // 组字结束：补一次 onChange，把最终中文交给父级
        onChange?.({
          ...e,
          target: e.currentTarget,
          currentTarget: e.currentTarget,
        } as ChangeEvent<HTMLInputElement>)
        onCompositionEnd?.(e)
      }}
    />
  )
})

export default ImeSafeInput
