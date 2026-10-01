import WelcomeBanner from './components/WelcomeBanner'

export default function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 selection:bg-indigo-500 selection:text-white">
      <main className="w-full flex flex-col items-center justify-center">
        <WelcomeBanner title="VIDYORA AI: Learn Smarter" />
      </main>
    </div>
  )
}
