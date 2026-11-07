"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatusPill } from "@/components/ui";

type State = "checking" | "connected" | "unavailable";

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
        setState("unavailable");
        setInfo("Local service is not reachable");
      });
    return () => {
      alive = false;
    };
  }, []);

  const tone = state === "connected" ? "verified" : state === "unavailable" ? "info" : "muted";
  const label =
    state === "checking"
      ? "Probing backend…"
      : state === "connected"
        ? "FastAPI Backend Connected"
        : "Backend unavailable";

  return (
    <div className="flex items-center gap-2">
      <StatusPill tone={tone as any} pulse={state === "connected"}>
        {label}
      </StatusPill>
      {info && <span className="font-mono text-2xs text-ink-faint">{info}</span>}
    </div>
  );
}
