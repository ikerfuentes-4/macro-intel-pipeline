import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import AuthGuard from "@/components/AuthGuard";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Macro Intelligence Engine",
  description: "Plataforma de inteligencia macroeconomica y geopolitica con track record verificable",
};

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/geopolitics", label: "Geopolitics" },
  { href: "/predictions", label: "Predictions" },
  { href: "/predictor", label: "Predictor" },
  { href: "/track-record", label: "Track Record" },
  { href: "/system", label: "System" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-slate-950 text-slate-200">
        <AuthGuard>
          <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h1 className="text-base font-semibold text-slate-100">Macro Intelligence Engine</h1>
                <p className="text-xs text-slate-500">
                  Evidencia &rarr; Razonamiento &rarr; Prediccion &rarr; Resultado, todo registrado
                </p>
              </div>
              <nav className="flex gap-1 text-sm">
                {NAV.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="px-3 py-1.5 rounded-md text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
            </div>
          </header>
          <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">{children}</main>
          <footer className="border-t border-slate-800 px-4 py-3 text-center text-xs text-slate-600">
            Herramienta de research macro y geopolitico. NO es asesoramiento de inversion personalizado.
          </footer>
        </AuthGuard>
      </body>
    </html>
  );
}
