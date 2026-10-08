"use client";

import { create } from "zustand";
import { findings as seedFindings, primaryRunSteps } from "./data";
import type { AgentStep, ReviewState, StepStatus } from "./types";

export type RunPhase = "idle" | "running" | "review" | "complete";

// Runtime copy of the run steps, each carrying a live status.
type LiveStep = AgentStep;

interface ReviewMap {
  [findingId: string]: ReviewState;
}

interface KavachState {
  phase: RunPhase;
  steps: LiveStep[];
  activeIndex: number;
  progress: number; // 0-100
  logLines: string[];
  externalTransfers: 0; // structurally always zero — sovereignty guarantee
  reviews: ReviewMap;
  showReport: boolean;
  _timers: ReturnType<typeof setTimeout>[];

  startRun: () => void;
  reset: () => void;
  setReview: (findingId: string, state: ReviewState) => void;
  openReport: () => void;
  closeReport: () => void;
}

// Speed factor so the whole run reads in ~30–40s but stays legible.
const SPEED = 1;

function initialSteps(): LiveStep[] {
  return primaryRunSteps.map((s) => ({ ...s, status: "pending" as StepStatus }));
}

function initialReviews(): ReviewMap {
  const m: ReviewMap = {};
  for (const f of seedFindings) m[f.id] = f.reviewState;
  return m;
}

export const useKavach = create<KavachState>((set, get) => ({
  phase: "idle",
  steps: initialSteps(),
  activeIndex: -1,
  progress: 0,
  logLines: [],
  externalTransfers: 0,
  reviews: initialReviews(),
  showReport: false,
  _timers: [],

  startRun: () => {
    const { _timers } = get();
    _timers.forEach(clearTimeout);

    const steps = initialSteps();
    set({
      phase: "running",
      steps,
      activeIndex: -1,
      progress: 0,
      logLines: ["› kavach run initiated — airgapped policy engaged"],
      showReport: false,
      _timers: [],
    });

    const timers: ReturnType<typeof setTimeout>[] = [];
    let elapsed = 400;
    const total = steps.reduce((a, s) => a + s.durationMs, 0);
    let accumulated = 0;

    steps.forEach((step, i) => {
      // activate
      timers.push(
        setTimeout(() => {
          set((st) => ({
            activeIndex: i,
            steps: st.steps.map((s, idx) => (idx === i ? { ...s, status: "active" } : s)),
            logLines: [...st.logLines, `› ${step.agent}: ${step.label}…`],
          }));
        }, elapsed * SPEED),
      );

      // complete
      const completeAt = elapsed + step.durationMs;
      accumulated += step.durationMs;
      const pct = Math.round((accumulated / total) * 100);
      timers.push(
        setTimeout(() => {
          const isLast = i === steps.length - 1;
          set((st) => ({
            progress: pct,
            steps: st.steps.map((s, idx) =>
              idx === i
                ? { ...s, status: (step.detail.includes("human review") ? "warn" : "done") as StepStatus }
                : s,
            ),
            logLines: [...st.logLines, `  ✓ ${step.detail}`],
          }));
          if (isLast) {
            set({ phase: "review", progress: 100 });
          }
        }, completeAt * SPEED),
      );

      elapsed = completeAt + 300;
    });

    set({ _timers: timers });
  },

  reset: () => {
    get()._timers.forEach(clearTimeout);
    set({
      phase: "idle",
      steps: initialSteps(),
      activeIndex: -1,
      progress: 0,
      logLines: [],
      showReport: false,
      reviews: initialReviews(),
      _timers: [],
    });
  },

  setReview: (findingId, state) =>
    set((st) => ({ reviews: { ...st.reviews, [findingId]: state } })),

  openReport: () => set({ showReport: true, phase: "complete" }),
  closeReport: () => set({ showReport: false }),
}));
