"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { BackendStatus } from "@/components/viz/BackendStatus";
export function TopBar() {
  const [clock, setClock] = useState("");
  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString());
    tick(); const id = setInterval(tick, 1000); return () => clearInterval(id);
  }, []);
  return <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-line bg-surface px-4">
    <BackendStatus /><div className="flex items-center gap-4"><span className="hidden text-xs text-ink-muted sm:block">{clock}</span><Link href="/workbench" className="btn btn-primary">Analyze documents</Link></div>
  </header>;
}
