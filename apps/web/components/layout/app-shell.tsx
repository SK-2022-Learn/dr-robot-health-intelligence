import { ProfileProvider } from "@/components/health/profile-context";
import { Sidebar } from "@/components/layout/sidebar";
import { TopHeader } from "@/components/layout/top-header";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ProfileProvider>
      <div className="app-shell">
        <Sidebar />
        <div className="app-main"><TopHeader /><main className="content">{children}</main></div>
      </div>
    </ProfileProvider>
  );
}
