import { useState } from 'react'

export default function App() {
  const [count, setCount] = useState<number>(0)

  const techStack = [
    { name: 'React 19', role: 'UI Library', status: 'Active' },
    { name: 'TypeScript', role: 'Type Safety', status: 'Active' },
    { name: 'Vite', role: 'Build Tool & Dev Server', status: 'Active' },
    { name: 'Tailwind CSS v4', role: 'Utility Styling', status: 'Active' },
  ]

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 selection:bg-indigo-500 selection:text-white">
      <main className="w-full max-w-xl bg-slate-900/80 border border-slate-800 rounded-2xl p-8 shadow-2xl backdrop-blur-sm space-y-6">
        {/* Header */}
        <div className="space-y-2 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            VIDYORA AI • Step 2 Frontend Foundation
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">
            Frontend Foundation Ready
          </h1>
          <p className="text-sm text-slate-400">
            React, TypeScript, Vite, and Tailwind CSS are installed and verified.
          </p>
        </div>

        {/* Tech Stack Verification Cards */}
        <div className="grid grid-cols-2 gap-3 pt-2">
          {techStack.map((tech) => (
            <div
              key={tech.name}
              className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/50 flex flex-col justify-between"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium text-sm text-slate-200">{tech.name}</span>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded-full">
                  {tech.status}
                </span>
              </div>
              <span className="text-xs text-slate-400">{tech.role}</span>
            </div>
          ))}
        </div>

        {/* React State & Interaction Test */}
        <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-slate-200">Reactivity Test</p>
            <p className="text-xs text-slate-400">Verifies React state & re-rendering</p>
          </div>
          <button
            type="button"
            onClick={() => setCount((prev) => prev + 1)}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white font-medium text-sm transition-all shadow-md shadow-indigo-600/20 cursor-pointer"
          >
            Clicks: <span className="font-bold ml-1">{count}</span>
          </button>
        </div>

        {/* Footer Note */}
        <div className="pt-2 text-center text-xs text-slate-500">
          Ready for VIDYORA AI module development.
        </div>
      </main>
    </div>
  )
}
