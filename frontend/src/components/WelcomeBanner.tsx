interface WelcomeBannerProps {
  title?: string
  subtitle?: string
  badgeText?: string
}

export default function WelcomeBanner({
  title = 'Welcome to VIDYORA AI',
  subtitle = 'Transform educational videos into structured notes, source-grounded answers, and interactive quizzes.',
  badgeText = 'AI-Powered Adaptive Learning',
}: WelcomeBannerProps) {
  return (
    <section className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-xl text-center space-y-4">
      {/* Status Badge */}
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
        <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
        {badgeText}
      </div>

      {/* Main Title */}
      <h1 className="text-3xl font-bold tracking-tight text-white">
        {title}
      </h1>

      {/* Subtitle / Description */}
      <p className="text-sm text-slate-400 leading-relaxed max-w-md mx-auto">
        {subtitle}
      </p>

      {/* Additional Note */}
      <div className="pt-2 flex items-center justify-center">
        <span className="text-xs text-slate-500">
          Ready to learn smarter with AI-assisted video intelligence.
        </span>
      </div>
    </section>
  )
}
