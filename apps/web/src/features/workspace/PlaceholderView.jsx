export function PlaceholderView({ view }) {
  return (
    <section className="workspace-card" aria-label={view.eyebrow}>
      <p>{view.eyebrow}</p>
      <h1>{view.title}</h1>
      <span>{view.body}</span>
      <div className="workspace-actions">
        {view.actions.map((action) => (
          <code key={action}>{action}</code>
        ))}
      </div>
    </section>
  )
}
