import type { AnalysisCatalog } from "./api";

/** Fallback profile catalog used when the backend is offline. */
export const sampleAnalysisCatalog: AnalysisCatalog = {
  profiles: [
    {
      id: "general",
      name: "General documents",
      description: "Broad review terms for reports, policies, correspondence, and records.",
    },
    {
      id: "industrial",
      name: "Industrial engineering",
      description: "Equipment integrity, maintenance, and process-safety terminology.",
    },
  ],
  analysis_modes: [
    {
      id: "risk_review",
      name: "Risk review",
      description: "Find risk-related statements, quote the source, and verify each excerpt.",
    },
    {
      id: "summary",
      name: "Summary",
      description: "Summarize extracted text or describe a supplied image; output is advisory.",
    },
    {
      id: "extract_fields",
      name: "Extract fields",
      description: "Extract dates, equipment identifiers, and measurements directly from text.",
    },
  ],
};
