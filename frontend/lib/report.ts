import { findings, evidence, FACILITY, UNIT, getEvidence } from "./data";

/** Build a plain-text sample review report from the bundled data. */
export function buildReportText(): string {
  const lines: string[] = [];
  const rule = "=".repeat(64);
  lines.push(rule);
  lines.push("KAVACH AI — ENGINEERING REVIEW REPORT");
  lines.push(`${FACILITY} · ${UNIT}`);
  lines.push("Classification: CONFIDENTIAL · Generated on-premise · Air-gapped");
  lines.push(rule, "");
  lines.push("EXECUTIVE SUMMARY");
  lines.push(
    "Cross-analysis of the Unit 4 inspection report against the plant P&ID and\n" +
      "engineering documentation identified 9 findings across 6 equipment items.\n" +
      "One high-severity item (P-101 outlet wall thickness) and one unverified\n" +
      "hypothesis require reviewer attention before approval. Overall verification\n" +
      "score 94%, with 8 of 9 findings backed by retrieved source evidence.",
  );
  lines.push("");
  lines.push("FINDINGS");
  for (const f of findings) {
    const ev = getEvidence(f.evidenceIds);
    lines.push(`  #${String(f.index).padStart(2, "0")} [${f.severity.toUpperCase()}] ${f.title}`);
    lines.push(`      ${f.detail}`);
    lines.push(
      `      confidence=${f.confidence}%  verified=${f.verified ? "yes" : "NO"}  equipment=${f.equipment.join(", ")}`,
    );
    if (ev.length) {
      lines.push(`      evidence: ${ev.map((e) => `${e.source} p.${e.page}`).join("; ")}`);
    } else {
      lines.push("      evidence: NONE — flagged for human judgement");
    }
    lines.push("");
  }
  lines.push("EVIDENCE APPENDIX");
  for (const e of evidence) {
    lines.push(`  [${e.id}] ${e.source} p.${e.page} (relevance ${e.relevance}%)`);
    lines.push(`      "${e.excerpt}"`);
  }
  lines.push("");
  lines.push("RECOMMENDATIONS");
  lines.push("  1. Re-gauge P-101 outlet nozzle and schedule repair at next turnaround.");
  lines.push("  2. Clean HX-301 shell side to recover thermal duty.");
  lines.push("  3. Calibrate PT-104 on T-101 (non safety-critical).");
  lines.push("  4. Continue monitoring T-101 corrosion allowance (11-yr remaining life).");
  lines.push("");
  lines.push("VERIFICATION");
  lines.push("  Verification score: 94%");
  lines.push("  Evidence-backed findings: 8/9");
  lines.push("  Requires human review: 1 (finding #09)");
  lines.push("");
  lines.push("HUMAN REVIEW");
  lines.push("  AI recommends. A reviewer decides. This report is a decision-support");
  lines.push("  artefact and is not an authoritative approval until signed off.");
  lines.push("");
  lines.push(rule);
  lines.push("Produced by KAVACH AI · open-weight local models · no data left the site.");
  lines.push(rule);
  return lines.join("\n");
}

export function downloadText(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
