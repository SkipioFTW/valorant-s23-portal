import type { Metadata } from "next";
import { Orbitron, Montserrat } from "next/font/google";
import "./globals.css";

const orbitron = Orbitron({
  variable: "--font-orbitron",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800", "900"],
});

const montserrat = Montserrat({
  variable: "--font-montserrat",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "S23 Portal | Valorant Tournament Hub",
  description: "Advanced tournament management and statistics portal for S23.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        suppressHydrationWarning
        className={`${orbitron.variable} ${montserrat.variable} antialiased selection:bg-val-red selection:text-white`}
      >
        <div className="relative min-h-screen">
          {/* Main Content */}
          <main className="relative z-10">
            {children}
          </main>

          {/* Background Ambient Glows */}
          <div className="fixed top-0 left-0 w-full h-full pointer-events-none -z-10 overflow-hidden">
            <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-val-red/10 blur-[120px] rounded-full" />
            <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-val-blue/5 blur-[120px] rounded-full" />
          </div>
        </div>
      </body>
    </html>
  );
}
