import type { ReactNode } from "react";

interface PageContainerProps {
  children: ReactNode;
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
}

export default function PageContainer({
  children,
  title,
  subtitle,
  actions,
}: PageContainerProps) {
  return (
    <main className="ml-64 pt-16 max-md:ml-0">
      <div className="min-h-[calc(100vh-64px)] bg-transparent p-6 md:p-8">
        {title && (
          <header className="mb-6 flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
              {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
            </div>
            {actions}
          </header>
        )}
        {children}
      </div>
    </main>
  );
}
