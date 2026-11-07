export default function WorkbenchLoading() {
  return (
    <div className="space-y-4" role="status" aria-live="polite">
      <div className="h-9 w-48 animate-pulse rounded bg-surface-inset" />
      <div className="h-12 animate-pulse rounded bg-surface-inset" />
      <div className="h-72 animate-pulse rounded bg-surface-inset" />
      <span className="sr-only">Loading Workbench</span>
    </div>
  );
}
