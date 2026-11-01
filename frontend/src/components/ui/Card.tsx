import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
}

export default function Card({
  children,
  className = "",
}: CardProps) {
  return (
    <div
      className={`
        rounded-2xl border border-slate-200/80 bg-white/90
        shadow-[0_10px_30px_rgba(15,23,42,0.05)]
        backdrop-blur-sm transition-all duration-200
        hover:-translate-y-0.5 hover:shadow-[0_16px_35px_rgba(59,130,246,0.10)]
        ${className}
      `}
    >
      {children}
    </div>
  );
}
