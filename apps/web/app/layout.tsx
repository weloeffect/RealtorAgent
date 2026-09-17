import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Horizon Homes Voice Concierge",
  description: "A private AI concierge for finding exceptional homes and arranging viewings.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
