import type { Metadata, Viewport } from "next";
import "./globals.css";
import { RegisterServiceWorker } from "./register-sw";
export const metadata: Metadata = { title: "AadeshSmart AI Event Assistant", description: "A calm, reliable workspace for Sangh event volunteers.", applicationName: "AadeshSmart", manifest: "/manifest.webmanifest", appleWebApp: { capable: true, title: "AadeshSmart", statusBarStyle: "default" }, icons: { icon: "/icon.svg", apple: "/icon.svg" } };
export const viewport: Viewport = { themeColor: "#f7f8f6", width: "device-width", initialScale: 1 };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body><RegisterServiceWorker />{children}</body></html>; }
