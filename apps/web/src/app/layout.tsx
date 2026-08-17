import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@aria/design-tokens/tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aria AI",
  description: "فضای کاری هوشمند برای تبدیل درخواست مشتری به Scope قابل تأیید"
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="fa" dir="rtl">
      <body>
        <a className="skip-link" href="#main-content">
          رفتن به محتوای اصلی
        </a>
        {children}
      </body>
    </html>
  );
}

