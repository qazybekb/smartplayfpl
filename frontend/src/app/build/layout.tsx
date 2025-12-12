import { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Squad Builder - Build Your FPL Team",
  description:
    "Build an optimised Fantasy Premier League squad with AI. Choose from 6 strategies: Balanced, Template, Differential, Form-Based, Value, and Fixture-Based. Generate a 15-player team instantly.",
  keywords: [
    "FPL squad builder",
    "FPL team builder",
    "Fantasy Premier League squad",
    "FPL AI team builder",
    "FPL draft helper",
    "FPL wildcard team",
    "FPL template team",
    "FPL differential squad",
    "build FPL team",
    "best FPL team",
  ],
  openGraph: {
    title: "AI Squad Builder - Build Your FPL Team | SmartPlay FPL",
    description:
      "Build an optimised Fantasy Premier League squad with AI. Choose from 6 strategies and get a complete 15-player team.",
    type: "website",
    url: "https://smartplayfpl.com/build",
    images: [
      {
        url: "/og-build.png",
        width: 1200,
        height: 630,
        alt: "SmartPlay FPL AI Squad Builder",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Squad Builder - Build Your FPL Team | SmartPlay FPL",
    description:
      "Build an optimised FPL squad with AI. 6 strategies, instant results.",
    images: ["/og-build.png"],
  },
  alternates: {
    canonical: "/build",
  },
};

export default function BuildLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
