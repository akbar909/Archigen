export default function Sidebar({ items = [], onSelect, onNewChat, user, onLogout }) {
  return (
    <aside className="glass-card h-full p-4 md:p-5 flex flex-col gap-4 w-full md:w-80 border border-slate-700/70">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-400">ArchiGen</p>
          <h2 className="text-lg font-semibold text-white">AI 3D Home Architect</h2>
        </div>
        <button
          className="bg-accent/80 hover:bg-accent text-white px-3 py-1 rounded-lg text-sm"
          onClick={onNewChat}
        >
          New
        </button>
      </div>

      <div className="glass-card bg-slate-900/60 border border-slate-800 rounded-xl p-3 text-slate-200 flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-accent to-sky-400 flex items-center justify-center text-slate-900 font-semibold">
          {user?.email?.[0]?.toUpperCase() || 'A'}
        </div>
        <div>
          <p className="text-xs text-slate-400">Signed in</p>
          <p className="text-sm font-semibold">{user?.email}</p>
        </div>
        <button onClick={onLogout} className="text-sm text-red-300 ml-auto">Logout</button>
      </div>

      <div className="flex-1 overflow-auto scroll-soft space-y-2 pr-1">
        {items.length === 0 && (
          <p className="text-slate-400 text-sm">No designs yet. Generate your first layout!</p>
        )}
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelect(item.id)}
            className="w-full text-left bg-slate-900/50 hover:bg-slate-800/90 border border-slate-700 rounded-lg px-3 py-2 text-slate-100"
          >
            <div className="text-sm font-semibold truncate">{item.prompt}</div>
            <div className="text-xs text-slate-400 flex gap-2">
              <span className="pill px-2 py-0.5 text-xs text-slate-100 bg-transparent">{item.style || '—'}</span>
              <span>
                {item.created_at ? new Date(item.created_at).toLocaleString() : ''}
              </span>
            </div>
          </button>
        ))}
      </div>
    </aside>
  )
}
