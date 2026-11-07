"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import {
  Activity, ArrowDown, ArrowDownRight, ArrowRight, ArrowUpRight,
  BookOpen, Check, ChevronDown, CircleCheck, Cpu, FileCheck2,
  FileSearch, FileText, Fingerprint, FolderOpen, Layers3,
  ListFilter, LockKeyhole, Menu, RefreshCw, ScanLine,
  ShieldCheck, ShieldHalf, Upload, X,
} from "lucide-react";
import { nav } from "@/components/shell/nav";
import { ArchitectureFlow } from "@/components/viz/ArchitectureFlow";
import { SourceChip } from "@/components/ui";
import { ProjectIntroduction, WorkflowExample, WorkspaceGuide } from "./ProjectGuide";
import { api, type AnalysisMode } from "@/lib/api";
import { useLive } from "@/lib/live";
import { useCases } from "@/lib/profiles";

const modes = [
  {
    id: "risk_review" as const, label: "Review risks", icon: FileSearch,
    title: "Find what needs a closer look.",
    description: "Find risk-related statements using the selected profile's vocabulary. Read the quoted passages and review what needs attention in the original document.",
    outputs: ["Source-linked findings", "Excerpt verification", "Human review decisions"],
    detail: "Spot issues. Check the context. Decide what comes next.",
    example: "Review this project document for delays, missing approvals, and open issues. Cite the source for each finding.",
  },
  {
    id: "summary" as const, label: "Summarize", icon: BookOpen,
    title: "Get to the heart of your document.",
    description: "Use your configured local model to summarize text or describe an image. Keep the original close by as you review the advisory output.",
    outputs: ["Local model summaries", "Text and image analysis", "Original document access"],
    detail: "Bring the main ideas, important details, and open questions into focus.",
    example: "Summarize this document in plain language, including important dates, decisions, and open questions.",
  },
  {
    id: "extract_fields" as const, label: "Extract fields", icon: ListFilter,
    title: "Turn scattered details into structure.",
    description: "Pull dates, amounts, contacts, identifiers, and measurements exactly as written, with source locations to help you check the details.",
    outputs: ["Structured document fields", "Source locations", "Downloadable reports"],
    detail: "Find the details you need, with a path back to where they came from.",
    example: "Extract dates, amounts, contacts, and reference identifiers exactly as written in this document.",
  },
];

const workflow = [
  { title: "Upload your document", text: "Start in Document Vault. Upload your file and preview the source you want to understand.", icon: Upload },
  { title: "Set up the analysis", text: "In Workbench, select the file, choose a domain profile and mode, then edit the suggested request.", icon: Cpu },
  { title: "Read and review", text: "Run the analysis. Inspect the results and source excerpts, then review any findings held for your decision.", icon: FileCheck2 },
  { title: "Keep the result", text: "Revisit the saved analysis in Agent Runs. Open Deliverables to download the generated reports.", icon: FolderOpen },
];

function Brand() {
  return <Link href="/" className="landing-brand" aria-label="KAVACH AI home">
    <span className="landing-brand-mark"><ShieldHalf size={25} strokeWidth={1.6} aria-hidden="true" /></span>
    <span>KAVACH<span className="landing-brand-ai"> AI</span><small>PRIVATE DOCUMENT INTELLIGENCE</small></span>
  </Link>;
}

function LandingHeader() {
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") { setOpen(false); toggleRef.current?.focus(); }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [open]);

  return <header className="landing-header">
    <div className="landing-container landing-header-inner">
      <Brand />
      <nav className="landing-desktop-nav" aria-label="Main navigation">
        <a href="#about">What it does</a><a href="#workflow">How it works</a><a href="#use-cases">Use cases</a><a href="#guide">Quick guide</a>
      </nav>
      <div className="landing-header-actions">
        <Link href="/workbench" className="landing-button landing-button-dark landing-header-cta">Open workspace <ArrowUpRight size={16} aria-hidden="true" /></Link>
        <button ref={toggleRef} className="landing-menu-toggle" aria-expanded={open} aria-controls="landing-mobile-menu" aria-label={open ? "Close navigation" : "Open navigation"} onClick={() => setOpen(!open)}>
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>
    </div>
    <nav id="landing-mobile-menu" hidden={!open} className="landing-mobile-menu" aria-label="Mobile navigation" onClick={(event) => { if ((event.target as HTMLElement).closest("a")) setOpen(false); }}>
      <a href="#about">What it does <ArrowDownRight size={15} /></a><a href="#platform">Analysis modes <ArrowDownRight size={15} /></a><a href="#workflow">How it works <ArrowDownRight size={15} /></a><a href="#use-cases">Use cases <ArrowDownRight size={15} /></a><a href="#guide">Quick guide <ArrowDownRight size={15} /></a>
      <p className="landing-kicker">Your workspace</p>
      <div className="landing-mobile-tools">{nav.filter((item) => item.href !== "/").map((item) => <Link href={item.href} key={item.href}>{item.label}<ArrowUpRight size={14} /></Link>)}</div>
    </nav>
  </header>;
}

function IntelligenceIllustration() {
  return <figure className="landing-illustration" aria-labelledby="intelligence-caption">
    <div className="landing-diagram-top"><span><span className="landing-small-dot" /> THE LOCAL ADVANTAGE</span><Fingerprint size={19} strokeWidth={1.4} aria-hidden="true" /></div>
    <div className="landing-diagram-canvas" aria-hidden="true">
      <svg className="landing-diagram-lines" viewBox="0 0 540 390" fill="none">
        <circle cx="270" cy="183" r="115" stroke="#9cae9e" strokeOpacity=".17" />
        <circle cx="270" cy="183" r="145" stroke="#9cae9e" strokeOpacity=".1" strokeDasharray="3 7" />
        <path d="M104 111H163Q185 111 185 134V165H225M315 202H356Q380 202 380 226V267H420" stroke="#cf825f" strokeWidth="1.5" strokeDasharray="4 5" className="landing-flow-line" />
        <path d="M270 82V128M270 239V304H154" stroke="#9cae9e" strokeOpacity=".4" strokeDasharray="3 5" />
        <circle cx="270" cy="82" r="4" fill="#db8e68" /><circle cx="154" cy="304" r="4" fill="#b5c2a4" />
        <path d="M24 24V8H40M500 8H516V24M24 354V370H40M500 370H516V354" stroke="#9cae9e" strokeOpacity=".4" />
        <path d="M239 183H301M270 152V214" stroke="#9cae9e" strokeOpacity=".12" />
      </svg>
      <div className="landing-document-stack"><div className="landing-document-back" /><div className="landing-document-front"><FileText size={26} strokeWidth={1.4} /><span>YOUR DOCUMENTS</span><i /><i /><i /><div><b>PDF</b><b>DOCX</b><b>IMG</b></div></div></div>
      <div className="landing-engine"><div className="landing-engine-icon"><ShieldHalf size={54} strokeWidth={1.1} /></div><strong>KAVACH AI</strong><span>LOCAL ANALYSIS</span><div className="landing-engine-pins">{Array.from({length: 7}, (_, i) => <i key={i} />)}</div></div>
      <div className="landing-evidence-note"><span><ScanLine size={14} /> EXTRACT & UNDERSTAND</span><span><Layers3 size={14} /> RETRIEVE & REASON</span></div>
      <div className="landing-result-card"><div><FileCheck2 size={18} /><span>READY FOR YOUR REVIEW</span></div><strong>Insights with a<br />path to the source.</strong><span className="landing-result-source"><Check size={12} /> Source-linked findings</span></div>
      <div className="landing-diagram-label"><LockKeyhole size={12} /> YOUR LOCAL WORKSPACE</div>
    </div>
    <figcaption id="intelligence-caption"><LockKeyhole size={14} aria-hidden="true" /><span>Your files. Your models. Your infrastructure.</span><span className="landing-diagram-index">FIG. 01</span></figcaption>
  </figure>;
}

async function fetchOverview() {
  const [rawDocuments, runs] = await Promise.all([api.documents(), api.runs()]);
  const documents: unknown[] = Array.isArray(rawDocuments) ? rawDocuments : rawDocuments.documents ?? [];
  return { documents, runs };
}

function WorkspaceSnapshot({ onRefresh }: { onRefresh: () => void }) {
  const { data, source, error } = useLive(fetchOverview, null);
  return <section id="workspace" className="landing-workspace landing-container" aria-labelledby="workspace-heading">
    <div className="landing-section-heading"><div><p className="landing-kicker">PICK UP WHERE YOU LEFT OFF</p><h2 id="workspace-heading">Your workspace, at a glance.</h2></div><SourceChip source={source} /></div>
    <div className="landing-workspace-grid">
      <div className="landing-stat"><FileText size={22} aria-hidden="true" /><strong>{data ? String(data.documents.length).padStart(2, "0") : "—"}</strong><span>Stored documents</span><Link href="/vault">Open Document Vault <ArrowUpRight size={14} aria-hidden="true" /></Link></div>
      <div className="landing-stat"><Activity size={22} aria-hidden="true" /><strong>{data ? String(data.runs.length).padStart(2, "0") : "—"}</strong><span>Recorded runs</span><Link href="/runs">Explore analysis history <ArrowUpRight size={14} aria-hidden="true" /></Link></div>
      <div className="landing-recent"><div className="landing-recent-heading"><h3>Recent activity</h3><Link href="/runs" aria-label="View all analysis runs">View all <ArrowUpRight size={14} aria-hidden="true" /></Link></div>
        <div aria-live="polite" aria-busy={source === "loading"}>
          {source === "loading" && <p className="landing-activity-message">Connecting to your local workspace…</p>}
          {source === "unavailable" && <div className="landing-activity-message"><p>Your local service is unavailable.</p><p className="landing-activity-help">Start the backend to see your documents and analysis history.</p><details className="landing-connection-detail"><summary>Connection details</summary><p>{error}</p></details><button onClick={onRefresh} className="landing-text-button"><RefreshCw size={13} aria-hidden="true" /> Try again</button></div>}
          {source === "live" && !data?.runs.length && <div className="landing-activity-message"><p>Your next insight starts with a document.</p><Link href="/vault" className="landing-text-link">Upload your first file <ArrowRight size={14} aria-hidden="true" /></Link></div>}
          {data?.runs.slice(0, 5).map((run) => <Link key={run.id} href={`/runs/${run.id}`} className="landing-run"><span><strong>Run #{run.id}</strong><small>{run.scenario || "Document analysis"}</small></span><span className="landing-run-status">{run.status.replace(/_/g, " ")}</span><ArrowUpRight size={15} aria-hidden="true" /></Link>)}
        </div>
      </div>
    </div>
  </section>;
}

export function LandingPage() {
  const [activeMode, setActiveMode] = useState<AnalysisMode>("risk_review");
  const [refresh, setRefresh] = useState(0);
  const selectedMode = modes.find((mode) => mode.id === activeMode)!;
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  function handleTabKey(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % modes.length;
    else if (event.key === "ArrowLeft") next = (index + modes.length - 1) % modes.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = modes.length - 1;
    else return;
    event.preventDefault(); setActiveMode(modes[next].id); tabRefs.current[next]?.focus();
  }

  return <div className="landing">
    <a className="landing-skip" href="#main-content">Skip to content</a>
    <LandingHeader />
    <main id="main-content" tabIndex={-1}>
      <section className="landing-hero landing-container" aria-labelledby="hero-heading">
        <div className="landing-hero-copy">
          <p className="landing-kicker"><span className="landing-kicker-line" /> LOCAL-FIRST. EVIDENCE-LED.</p>
          <h1 id="hero-heading">Your documents.<br />Clearer insights.<br /><span>Your control.</span></h1>
          <p className="landing-hero-description">KAVACH AI is a private document analysis workspace. Review risks, summarize reports, and extract key details using local AI, with source evidence you can check.</p>
          <div className="landing-hero-actions"><Link href="/vault" className="landing-button landing-button-orange"><Upload size={17} aria-hidden="true" /> Upload a document <ArrowUpRight size={17} aria-hidden="true" /></Link><a href="#workflow" className="landing-text-link">See how it works <ArrowDown size={15} aria-hidden="true" /></a></div>
          <p className="landing-hero-note"><LockKeyhole size={13} aria-hidden="true" /> Built to run on your own infrastructure.</p>
        </div>
        <IntelligenceIllustration />
      </section>

      <div className="landing-principles landing-container" aria-label="Platform principles">
        <div><span className="landing-principle-icon"><Cpu size={21} strokeWidth={1.5} aria-hidden="true" /></span><span><strong>Intelligence that stays local</strong><small>Read text and scans with your local tools.</small></span></div>
        <div><span className="landing-principle-icon"><FileCheck2 size={21} strokeWidth={1.5} aria-hidden="true" /></span><span><strong>Evidence you can follow</strong><small>Source excerpts alongside your findings.</small></span></div>
        <div><span className="landing-principle-icon"><ShieldCheck size={21} strokeWidth={1.5} aria-hidden="true" /></span><span><strong>The final call stays yours</strong><small>Human review is part of the workflow.</small></span></div>
      </div>

      <ProjectIntroduction />

      <section id="platform" className="landing-platform landing-container" aria-labelledby="platform-heading">
        <div className="landing-section-heading"><div><p className="landing-kicker">LESS SEARCHING. MORE UNDERSTANDING.</p><h2 id="platform-heading">Find the signal in your documents.</h2></div><p>One workspace. Three ways to get<br className="landing-desktop-break" /> closer to what matters.</p></div>
        <div className="landing-mode-tabs" role="tablist" aria-label="Explore analysis modes">{modes.map((mode, index) => <button key={mode.id} ref={(element) => { tabRefs.current[index] = element; }} id={`tab-${mode.id}`} role="tab" aria-selected={activeMode === mode.id} aria-controls={`panel-${mode.id}`} tabIndex={activeMode === mode.id ? 0 : -1} onClick={() => setActiveMode(mode.id)} onKeyDown={(event) => handleTabKey(event, index)}><mode.icon size={18} aria-hidden="true" />{mode.label}<ArrowUpRight size={16} className="landing-tab-arrow" aria-hidden="true" /></button>)}</div>
        {modes.map((mode) => <div key={mode.id} id={`panel-${mode.id}`} role="tabpanel" aria-labelledby={`tab-${mode.id}`} hidden={activeMode !== mode.id} tabIndex={0} className="landing-mode-panel">
          <div className="landing-mode-copy"><span className="landing-section-number">0{modes.indexOf(mode) + 1} / ANALYSIS MODE</span><h3>{mode.title}</h3><p>{mode.description}</p><div className="landing-example-request"><span>EXAMPLE REQUEST</span><blockquote>{mode.example}</blockquote></div><Link href={`/workbench?mode=${mode.id}`} className="landing-text-link">Open in Workbench <ArrowUpRight size={16} aria-hidden="true" /></Link></div>
          <div className="landing-mode-preview"><div className="landing-preview-label"><span className="landing-small-dot" /> WORKFLOW PREVIEW <mode.icon size={18} aria-hidden="true" /></div><div className="landing-preview-path"><span><FileText size={19} aria-hidden="true" /> Your document</span><ArrowRight size={18} aria-hidden="true" /><span><ShieldHalf size={20} aria-hidden="true" /> Local analysis</span></div><p>{mode.detail}</p><ul>{mode.outputs.map((output) => <li key={output}><CircleCheck size={16} aria-hidden="true" />{output}</li>)}</ul><div className="landing-preview-footer"><LockKeyhole size={12} aria-hidden="true" /> PROCESSED IN YOUR LOCAL WORKSPACE</div></div>
        </div>)}
        <p className="landing-analysis-note">{selectedMode.id === "summary" ? "Model summaries and visual observations are advisory. Review them against the original document." : "Source verification checks citation support. Review findings in context before acting."}</p>
      </section>

      <section id="workflow" className="landing-workflow" aria-labelledby="workflow-heading"><div className="landing-container">
        <div className="landing-section-heading"><div><p className="landing-kicker">FROM FILE TO FINDING</p><h2 id="workflow-heading">A clear process. A traceable result.</h2></div><span className="landing-workflow-label"><LockKeyhole size={13} aria-hidden="true" /> ALL IN YOUR LOCAL WORKSPACE</span></div>
        <ol className="landing-steps">{workflow.map((step, index) => <li key={step.title}><div className="landing-step-top"><span>0{index + 1}</span><step.icon size={22} strokeWidth={1.4} aria-hidden="true" /></div><h3>{step.title}</h3><p>{step.text}</p>{index < workflow.length - 1 && <ArrowRight className="landing-step-arrow" size={18} aria-hidden="true" />}</li>)}</ol>
        <WorkflowExample />
        <details className="landing-pipeline"><summary>How the agents work together <ChevronDown size={16} aria-hidden="true" /></summary><div className="landing-pipeline-content"><div><h3>A visible process, step by step.</h3><p>Specialized agents handle document reading, planning, retrieval, reasoning, and source verification. Retrieval means finding relevant passages in your stored documents; configured local models provide text reasoning and image analysis.</p><p>Workbench shows each stage as it runs. The optional bounded planner chooses from allowed tools within step limits. You can inspect its actions in the saved run and review findings that need a human decision.</p><Link href="/workbench" className="landing-text-link">Explore Workbench <ArrowUpRight size={15} aria-hidden="true" /></Link></div><ArchitectureFlow /></div></details>
      </div></section>

      <section id="use-cases" className="landing-use-cases landing-container" aria-labelledby="use-cases-heading"><div className="landing-section-heading"><div><p className="landing-kicker">BUILT AROUND YOUR CONTEXT</p><h2 id="use-cases-heading">Different documents.<br />One private workspace.</h2></div><p>Start with a profile that fits your work.<br className="landing-desktop-break" /> Bring your own documents and questions.</p></div>
        <div className="landing-profile-grid">{useCases.map((item, index) => <Link key={item.profile} href={`/workbench?profile=${item.profile}`} className="landing-profile"><div><span className="landing-profile-number">0{index + 1}</span><ArrowUpRight size={18} aria-hidden="true" /></div><h3>{item.title}</h3><p>{item.description}</p><span className="landing-profile-mode">Suggested: {item.mode === "risk_review" ? "Risk review" : item.mode === "summary" ? "Summary" : "Extract fields"}</span></Link>)}</div>
      </section>

      <WorkspaceGuide />

      <WorkspaceSnapshot key={refresh} onRefresh={() => setRefresh((value) => value + 1)} />

      <section className="landing-final-cta landing-container" aria-labelledby="cta-heading"><div><p className="landing-kicker">YOUR NEXT DOCUMENT, UNDERSTOOD.</p><h2 id="cta-heading">Good insights start<br />with your own evidence.</h2><p>Bring a file. Choose your question. Stay in control.</p></div><div><Link href="/vault" className="landing-button landing-button-dark"><Upload size={17} aria-hidden="true" /> Upload a document <ArrowUpRight size={17} aria-hidden="true" /></Link><Link href="/workbench" className="landing-text-link">Or open your Workbench <ArrowRight size={15} aria-hidden="true" /></Link></div><ShieldHalf className="landing-cta-watermark" size={280} strokeWidth={.6} aria-hidden="true" /></section>
    </main>
    <footer className="landing-footer"><div className="landing-container"><div className="landing-footer-top"><div><Brand /><p>Document intelligence.<br />On your terms.</p></div><nav aria-label="Workspace tools"><p className="landing-kicker">EXPLORE YOUR WORKSPACE</p><div>{nav.filter((item) => item.href !== "/").map((item) => <Link key={item.href} href={item.href}>{item.label}<ArrowUpRight size={12} aria-hidden="true" /></Link>)}</div></nav></div><div className="landing-footer-bottom"><span>KAVACH AI · Private document intelligence</span><span><LockKeyhole size={12} aria-hidden="true" /> Local tools. Traceable sources. Human judgment.</span></div></div></footer>
  </div>;
}
