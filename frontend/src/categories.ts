// Shared category icons. Source of truth for the timeline, cards, legend and globe.
// Icons describe the TYPE of event; they never represent forces, weapons, fronts or routes.
// Paths are stroke-based on a 24x24 viewBox so they can be drawn with SVG or canvas Path2D.

export type CategoryMeta = { key: string; label: string; color: string; path: string }

export const CATEGORIES: Record<string, CategoryMeta> = {
  conflicto: { key: 'conflicto', label: 'Conflicto armado', color: '#e0805f', path: 'M12 2l2.2 5.6L20 6l-3 5 5 3-5.8.9L17 21l-5-3.5L7 21l.8-6.1L2 14l5-3-3-5 5.8 1.6z' },
  ataque: { key: 'ataque', label: 'Ataque', color: '#ec6b6b', path: 'M17 12a5 5 0 1 1-10 0a5 5 0 1 1 10 0zM12 2v5M12 17v5M2 12h5M17 12h5' },
  humanitario: { key: 'humanitario', label: 'Situación humanitaria', color: '#e8c46a', path: 'M3 20L12 4l9 16zM12 4v16M9 20l3-5 3 5' },
  desplazamiento: { key: 'desplazamiento', label: 'Desplazamiento', color: '#e0a868', path: 'M10 5a2 2 0 1 1-4 0a2 2 0 1 1 4 0zM8 9v6l-2 5M8 15l3 5M8 11l3-1M14 12h7M18 9l3 3-3 3' },
  negociacion: { key: 'negociacion', label: 'Negociación', color: '#86bfe0', path: 'M3 5h11v7H8l-3 3v-3H3zM10 15v2h6l3 3v-3h2v-7h-4' },
  acuerdo: { key: 'acuerdo', label: 'Acuerdo', color: '#93d29e', path: 'M6 3h9l4 4v14H6zM15 3v4h4M9 14l2 2 4-4' },
  politica: { key: 'politica', label: 'Decisión política', color: '#bfa9e6', path: 'M3 9l9-5 9 5M5 9v9M10 9v9M14 9v9M19 9v9M3 20h18' },
  vencimiento: { key: 'vencimiento', label: 'Vencimiento', color: '#cfc8ad', path: 'M21 12a9 9 0 1 1-18 0a9 9 0 1 1 18 0zM12 7v5l3 2' },
  clima: { key: 'clima', label: 'Clima y diplomacia', color: '#f0c96b', path: 'M16 12a4 4 0 1 1-8 0a4 4 0 1 1 8 0zM12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2' },
}

const FALLBACK: CategoryMeta = { key: 'otro', label: 'Actualidad internacional', color: '#d7a964', path: 'M18 12a6 6 0 1 1-12 0a6 6 0 1 1 12 0z' }

export const categoryMeta = (category?: string | null): CategoryMeta => CATEGORIES[category ?? ''] ?? FALLBACK
