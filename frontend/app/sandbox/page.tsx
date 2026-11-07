"use client";

import { useCallback, useEffect, useState } from "react";
import { Panel, PanelHeader, PageTitle, StatusPill } from "@/components/ui";
import { api, type SandboxResult, type SandboxStatus } from "@/lib/api";

export default function SandboxPage() {
  const [status, setStatus] = useState<SandboxStatus | null>(null);
  const [code, setCode] = useState("");
  const [stdin, setStdin] = useState("");
  const [timeout, setTimeoutSeconds] = useState(10);
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(true);
  const [result, setResult] = useState<SandboxResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setChecking(true);
    try {
      const value = await api.sandboxStatus();
      setStatus(value);
      setTimeoutSeconds((current) => Math.min(current, value.limits.timeout_seconds));
      setError(null);
    } catch (err) {
      setStatus(null);
      setError(err instanceof Error ? err.message : "Sandbox status unavailable");
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  async function execute() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.executeCode(code, stdin, timeout));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Execution failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageTitle eyebrow="Isolated code execution" title="Python Sandbox">
        <StatusPill tone={status?.available ? "verified" : "muted"}>
          {checking ? "Checking runtime" : status?.status ?? "Unavailable"}
        </StatusPill>
      </PageTitle>

      <Panel className="mb-4">
        <PanelHeader title="Execution environment" right={
          <button className="btn btn-ghost" onClick={refresh} disabled={checking || busy}>Refresh status</button>
        } />
        <div className="space-y-2 p-4 text-sm text-ink-muted">
          <p>{status?.reason ?? "Connect the local backend to check the execution environment."}</p>
          {status && <p>
            Network disabled. No access to uploaded files or host folders.
            Non-root Python worker with {status.limits.memory_mb} MB memory,
            {" "}{status.limits.timeout_seconds}s maximum runtime, and {status.limits.output_bytes / 1024} KB output.
            Temporary files are discarded after each run.
          </p>}
          {status && !status.available && <p>
            Follow the sandbox setup instructions in the project README, then refresh this status.
          </p>}
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="Run Python" sub="Python standard library only. Code runs when you press Run code." />
        <form onSubmit={(event) => { event.preventDefault(); void execute(); }} className="space-y-4 p-4">
          <label className="block">
            <span className="eyebrow mb-2 block">Python code</span>
            <textarea aria-label="Python code" value={code} onChange={(event) => setCode(event.target.value)}
              disabled={busy} rows={14} maxLength={65536} spellCheck={false}
              className="w-full rounded border border-line bg-surface-inset p-3 font-mono text-sm"
              placeholder="Enter Python code to execute" />
          </label>
          <div className="grid gap-4 sm:grid-cols-[1fr_160px]">
            <label className="block">
              <span className="eyebrow mb-2 block">Standard input (optional)</span>
              <textarea aria-label="Standard input" value={stdin} onChange={(event) => setStdin(event.target.value)}
                disabled={busy} rows={3} maxLength={16384}
                className="w-full rounded border border-line bg-surface-inset p-3 font-mono text-sm" />
            </label>
            <label className="block">
              <span className="eyebrow mb-2 block">Timeout (seconds)</span>
              <input type="number" min={1} max={status?.limits.timeout_seconds ?? 10} value={timeout}
                onChange={(event) => setTimeoutSeconds(Number(event.target.value))} disabled={busy}
                className="w-full rounded border border-line bg-surface-inset p-3 text-sm" />
            </label>
          </div>
          <button type="submit" className="btn btn-primary"
            disabled={busy || checking || !status?.available || !code.trim() || !Number.isInteger(timeout) || timeout < 1}>
            {busy ? "Executing..." : "Run code"}
          </button>
          {busy && <p role="status" className="text-sm text-ink-muted">Running in a temporary isolated container...</p>}
          {error && <p role="alert" className="text-sm text-danger">{error}</p>}
        </form>
      </Panel>

      {result && <Panel className="mt-4">
        <PanelHeader title="Execution result" sub={`Exit: ${result.exit_code ?? "unavailable"} / ${result.duration_ms} ms`}
          right={<StatusPill tone={result.status === "completed" ? "verified" : "caution"}>
            {result.status.replaceAll("_", " ")}
          </StatusPill>} />
        <div aria-live="polite" className="space-y-4 p-4">
          <Output title="Standard output" text={result.stdout} />
          <Output title="Standard error" text={result.stderr} />
          {result.output_truncated && <p className="text-sm text-caution">Output limit reached; execution was stopped.</p>}
        </div>
      </Panel>}
    </div>
  );
}

function Output({ title, text }: { title: string; text: string }) {
  return <div><p className="eyebrow mb-2">{title}</p>
    <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded border border-line bg-surface-inset p-3 font-mono text-xs">
      {text || "(empty)"}
    </pre>
  </div>;
}
