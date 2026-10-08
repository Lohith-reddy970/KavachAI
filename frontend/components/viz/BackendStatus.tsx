"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusPill } from "@/components/ui";

type State = "checking" | "connected" | "standalone";

/**
 * Live probe of the optional FastAPI backend. Never blocks the sample workflow: if the
 * backend is offline the UI simply reports it is running standalone on the
 * local mock-inference layer.
 */
export function BackendStatus() {
  const [state, setState] = useState<State>("checking");
  const [info, setInfo] = useState<string>("");

  useEffect(() => {
    let alive = true;
    api
      .health()
      .then((h) => {
        if (!alive) return;
        setState("connected");
        setInfo(`mode=${h.mode} · v${h.version}`);
      })
      .catch(() => {
        if (!alive) return;
        setState("standalone");
        setInfo("mock inference layer");
      });
    return () => {
      alive = false;
    };
  }, []);

  const tone = state === "connected" ? "verified" : state === "standalone" ? "info" : "muted";
  const label =
    state === "checking"
      ? "Probing backend…"
      : state === "connected"
        ? "FastAPI Backend Connected"
        : "Standalone (Mock Inference)";

  return (
    <div className="flex items-center gap-2">
      <StatusPill tone={tone as any} pulse={state === "connected"}>
        {label}
      </StatusPill>
      {info && <span className="font-mono text-2xs text-ink-faint">{info}</span>}
    </div>
  );
}
