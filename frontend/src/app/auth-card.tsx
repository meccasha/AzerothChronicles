import Link from "next/link";
import { Logo } from "@/components/layout/logo";

export function AuthCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="w-full max-w-md animate-rise rounded-2xl border border-gold/20 bg-card/90 p-7 shadow-2xl parchment">
        <Link href="/" className="mb-6 flex items-center justify-center gap-2">
          <Logo size={36} />
        </Link>
        <h1 className="text-center text-2xl font-bold gold-text">{title}</h1>
        <p className="mb-6 mt-1 text-center text-sm text-muted-foreground">{subtitle}</p>
        {children}
      </div>
    </div>
  );
}
