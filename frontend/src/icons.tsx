import { categoryMeta } from './categories'

export function CategoryIcon({ category, size = 18, title }: { category?: string | null; size?: number; title?: string }) {
  const meta = categoryMeta(category)
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={meta.color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
      role={title ? 'img' : undefined} aria-hidden={title ? undefined : true} aria-label={title} focusable="false">
      <path d={meta.path} />
    </svg>
  )
}
