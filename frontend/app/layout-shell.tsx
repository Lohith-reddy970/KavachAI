import { Sidebar } from "@/components/shell/Sidebar";
import { TopBar } from "@/components/shell/TopBar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <div className="pl-14 md:pl-[236px]">
        <TopBar />
        <main className="page-enter mx-auto max-w-[1400px] px-3 py-4 sm:px-4 sm:py-5 md:px-6 md:py-6">
          {children}
        </main>
      </div>
    </div>
  );
}
