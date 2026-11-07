import type { AnalysisCatalog } from "./api";

/** Built-in analysis settings, matching the backend profile catalog. */
export const defaultAnalysisCatalog: AnalysisCatalog = {
  profiles: [
    {
      id: "general",
      name: "General / everyday documents",
      description: "A starting point for any document: notes, reports, letters, and personal records.",
    },
    {
      id: "industrial",
      name: "Industrial engineering",
      description: "Equipment integrity, maintenance, and process-safety terminology.",
    },
    { id: "business", name: "Business & projects", description: "Project updates, meeting notes, suppliers, deadlines, and approvals." },
    { id: "education", name: "Education & research", description: "Assignments, course notes, research reports, and academic administration." },
    { id: "finance", name: "Finance & procurement", description: "Invoices, expense records, budgets, payments, and purchase requests." },
    { id: "legal", name: "Contracts & policies", description: "Agreements, obligations, renewals, and policy documents." },
    { id: "healthcare", name: "Healthcare administration", description: "Administrative records, scheduling, consent forms, and service procedures." },
    { id: "hr", name: "People & HR", description: "Onboarding, staff policies, training records, and leave administration." },
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
      description: "Extract dates, amounts, contacts, owners, reference IDs, and measurements with source citations.",
    },
  ],
};

export const useCases = [
  { profile: "industrial", title: "Industry & engineering", description: "Inspection reports, maintenance, equipment manuals, and safety records.", mode: "risk_review" as const, request: "Review this industrial document for equipment integrity, maintenance, and safety issues. Cite the source for each finding." },
  { profile: "general", title: "Everyday documents", description: "Understand letters, personal records, reports, and scanned documents.", mode: "summary" as const, request: "Summarize this document in plain language, including important dates, decisions, and open questions." },
  { profile: "business", title: "Business & projects", description: "Find delays, missing approvals, and open issues in project notes.", mode: "risk_review" as const, request: "Review this project document for delays, missing approvals, and open issues. Cite the source for each finding." },
  { profile: "education", title: "Education & research", description: "Summarize study material, research notes, and academic reports.", mode: "summary" as const, request: "Summarize this educational document's purpose, main ideas, important dates, and stated limitations." },
  { profile: "finance", title: "Finance & procurement", description: "Extract invoice dates, amounts, contacts, and reference numbers.", mode: "extract_fields" as const, request: "Extract the dates, currency amounts, contacts, owners, and reference identifiers exactly as written in this document." },
  { profile: "legal", title: "Contracts & policies", description: "Locate obligations, renewals, exceptions, and terms needing attention.", mode: "risk_review" as const, request: "Review this contract or policy for obligations, renewal dates, exceptions, and issues needing attention. Cite the relevant passages." },
  { profile: "healthcare", title: "Healthcare administration", description: "Summarize administrative records, forms, and service procedures.", mode: "summary" as const, request: "Summarize this healthcare administrative document, including dates, consent details, and missing information. Use only the document." },
  { profile: "hr", title: "People & HR", description: "Review onboarding, training, leave, and staff-policy documents.", mode: "risk_review" as const, request: "Review this HR document for incomplete records, training gaps, overdue actions, and policy issues. Cite each supporting passage." },
];
