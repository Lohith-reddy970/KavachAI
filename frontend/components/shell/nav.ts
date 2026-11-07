import {
  LayoutDashboard,
  TerminalSquare,
  Vault,
  Database,
  Activity,
  Waypoints,
  ShieldCheck,
  FileOutput,
  Server,
  MessagesSquare,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  code: string;
  icon: LucideIcon;
}

export const nav: NavItem[] = [
  { href: "/", label: "Overview", code: "OV", icon: LayoutDashboard },
  { href: "/workbench", label: "Workbench", code: "WB", icon: TerminalSquare },
  { href: "/sandbox", label: "Python Sandbox", code: "SB", icon: TerminalSquare },
  { href: "/vault", label: "Document Vault", code: "DV", icon: Vault },
  { href: "/knowledge", label: "Knowledge Base", code: "KB", icon: Database },
  { href: "/chat", label: "Document Chat", code: "CH", icon: MessagesSquare },
  { href: "/runs", label: "Agent Runs", code: "AR", icon: Activity },
  { href: "/router", label: "Model Router", code: "MR", icon: Waypoints },
  { href: "/security", label: "Security Center", code: "SC", icon: ShieldCheck },
  { href: "/deliverables", label: "Deliverables", code: "DL", icon: FileOutput },
  { href: "/system", label: "System", code: "SY", icon: Server },
];
