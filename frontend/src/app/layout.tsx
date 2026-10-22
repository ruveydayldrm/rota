import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Figtree, JetBrains_Mono } from "next/font/google";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

const display = Bricolage_Grotesque({
  subsets: ["latin", "latin-ext"],
  weight: ["600", "700", "800"],
  variable: "--font-bricolage",
  display: "swap",
});
const body = Figtree({ subsets: ["latin", "latin-ext"], variable: "--font-figtree", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin", "latin-ext"], variable: "--font-jetbrains", display: "swap" });

export const metadata: Metadata = {
  title: "Rota — Sohbetle rota kuran şehir rehberi",
  description: "Ne sevdiğini söyle, günü haritada kuralım. Gerçek OpenStreetMap mekanlarıyla yapay zekâ destekli gezi rotaları.",
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#e9eef0" },
    { media: "(prefers-color-scheme: dark)", color: "#0e161a" },
  ],
};

// Sayfa boyanmadan önce kayıtlı temayı uygular (renk sıçramasını önler).
const themeScript = `try{var t=localStorage.getItem('rota-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" suppressHydrationWarning className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
