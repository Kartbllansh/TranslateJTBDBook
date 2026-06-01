import type { Metadata } from "next";
import type { ReactNode } from "react";

import { bookDescription, bookTitle } from "@/lib/book-data";

import "./globals.css";

export const metadata: Metadata = {
  title: `${bookTitle} | Читалка`,
  description: bookDescription,
  openGraph: {
    title: bookTitle,
    description: bookDescription,
    type: "article",
    locale: "ru_RU"
  }
};

export default function RootLayout({
  children
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
