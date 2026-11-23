import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function manifest(): MetadataRoute.Manifest { return { name: "AadeshSmart AI Event Assistant", short_name: "AadeshSmart", description: "A calm, reliable workspace for Sangh event volunteers.", start_url: "/", display: "standalone", background_color: "#f7f8f6", theme_color: "#f7f8f6", icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable" }] }; }
