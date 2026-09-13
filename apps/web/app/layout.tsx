import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Horizon Homes Voice Concierge",
  description: "Local mocked real-estate voice agent",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

