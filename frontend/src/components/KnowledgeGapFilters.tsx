import React, { useMemo } from 'react'
import type { ChunkKnowledgeGap } from '../types/ai'

export type FilterCategory = 'ALL' | 'WEAK' | 'DEVELOPING' | 'STRONG'

interface KnowledgeGapFiltersProps {
  activeFilter: FilterCategory
  onFilterChange: (filter: FilterCategory) => void
  gaps: ChunkKnowledgeGap[]
}

export const KnowledgeGapFilters: React.FC<KnowledgeGapFiltersProps> = ({
  activeFilter,
  onFilterChange,
  gaps,
}) => {
  const counts = useMemo(() => {
    return {
      ALL: gaps.length,
      WEAK: gaps.filter((g) => g.classification === 'WEAK').length,
      DEVELOPING: gaps.filter((g) => g.classification === 'DEVELOPING').length,
      STRONG: gaps.filter((g) => g.classification === 'STRONG').length,
    }
  }, [gaps])

  const filterOptions: { id: FilterCategory; label: string; count: number; colorClass: string }[] = [
    {
      id: 'ALL',
      label: 'All Concepts',
      count: counts.ALL,
      colorClass: activeFilter === 'ALL' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white',
    },
    {
      id: 'WEAK',
      label: 'Needs Revision',
      count: counts.WEAK,
      colorClass: activeFilter === 'WEAK' ? 'bg-rose-600 text-white' : 'text-rose-400 hover:text-rose-300',
    },
    {
      id: 'DEVELOPING',
      label: 'Developing',
      count: counts.DEVELOPING,
      colorClass: activeFilter === 'DEVELOPING' ? 'bg-amber-600 text-white' : 'text-amber-400 hover:text-amber-300',
    },
    {
      id: 'STRONG',
      label: 'Mastered',
      count: counts.STRONG,
      colorClass: activeFilter === 'STRONG' ? 'bg-emerald-600 text-white' : 'text-emerald-400 hover:text-emerald-300',
    },
  ]

  return (
    <div className="flex items-center gap-1.5 border-b border-slate-800 pb-2 overflow-x-auto text-xs">
      <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider mr-1 shrink-0">
        Filter By:
      </span>
      {filterOptions.map((opt) => (
        <button
          key={opt.id}
          type="button"
          onClick={() => onFilterChange(opt.id)}
          className={`px-2.5 py-1 rounded-lg font-medium transition cursor-pointer shrink-0 flex items-center gap-1.5 ${
            opt.colorClass
          } ${activeFilter === opt.id ? 'shadow-sm' : 'bg-slate-900/60 hover:bg-slate-800'}`}
          aria-pressed={activeFilter === opt.id}
        >
          <span>{opt.label}</span>
          <span className="text-[10px] opacity-75 font-mono">({opt.count})</span>
        </button>
      ))}
    </div>
  )
}

export default KnowledgeGapFilters
