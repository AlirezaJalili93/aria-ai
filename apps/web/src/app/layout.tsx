import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@aria/design-tokens/tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aria AI — پلتفرم تبدیل بریف به Scope تأییدشده",
  description: "فضای کاری هوشمند برای آژانس‌های وب و فریلنسرها جهت تبدیل ورودی‌های مبهم مشتری به نیازمندی‌های ساختاریافته، کشف ابهام‌ها و تصویب رسمی Scope",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="fa" dir="rtl">
      <body data-theme="dark">
        <a className="skip-link" href="#main-content">
          رفتن به محتوای اصلی
        </a>
        {children}
      </body>
    </html>
  );
}
