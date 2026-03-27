import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Toaster } from "react-hot-toast";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "WhatsApp Insight Transcriber",
  description:
    "Plataforma avançada de transcrição e análise de conversas do WhatsApp com IA",
  keywords: ["whatsapp", "transcrição", "IA", "análise", "Claude"],
  themeColor: "#0a0a14",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className="dark">
      <body className={`${inter.className} bg-dark-900 text-white antialiased`}>
        <div className="relative min-h-screen bg-grid">
          {/* Ambient Background Effects */}
          <div className="fixed inset-0 pointer-events-none overflow-hidden">
            <div className="absolute -top-40 -right-40 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl" />
            <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-accent-400/10 rounded-full blur-3xl" />
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-brand-600/5 rounded-full blur-3xl" />
          </div>
          
          <div className="relative z-10">
            {children}
          </div>
        </div>
        
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: "#1a1a35",
              color: "#e8e8f0",
              border: "1px solid rgba(108,99,255,0.3)",
              borderRadius: "12px",
              fontSize: "14px",
            },
            success: {
              iconTheme: { primary: "#00d4aa", secondary: "#0a0a14" },
            },
            error: {
              iconTheme: { primary: "#ff6b6b", secondary: "#0a0a14" },
            },
          }}
        />
      </body>
    </html>
  );
}
