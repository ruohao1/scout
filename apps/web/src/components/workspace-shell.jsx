export function WorkspaceShell({ children, rightPane = null, rightPaneLabel = 'Workspace', rightPaneTone = 'neutral', className = '' }) {
  const hasRightPane = Boolean(rightPane)
  const classes = ['workspace-shell', className].filter(Boolean).join(' ')

  return (
    <section className={classes} data-right-open={hasRightPane} data-tone={rightPaneTone}>
      <div className="workspace-shell-main">
        {children}
      </div>
      {hasRightPane && (
        <aside className="workspace-shell-aside" aria-label={rightPaneLabel}>
          {rightPane}
        </aside>
      )}
    </section>
  )
}
