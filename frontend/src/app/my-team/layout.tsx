import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Analyse Your FPL Team",
  description:
    "Get AI-powered analysis of your Fantasy Premier League team. Enter your FPL Team ID for personalised transfer recommendations, captain picks, lineup optimisation, and chip strategy.",
  keywords: [
    "FPL team analysis",
    "analyse FPL team",
    "FPL team ID",
    "FPL recommendations",
    "FPL transfer advice",
    "FPL captain picks",
    "FPL lineup optimiser",
    "my FPL team",
    "FPL assistant",
    "FPL AI analysis",
  ],
  openGraph: {
    title: "Analyse Your FPL Team | SmartPlay FPL",
    description:
      "Get AI-powered analysis of your FPL team. Transfer recommendations, captain picks, and more.",
    type: "website",
    url: "https://smartplayfpl.com/my-team",
    images: [
      {
        url: "/og-team.png",
        width: 1200,
        height: 630,
        alt: "SmartPlay FPL Team Analysis",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Analyse Your FPL Team | SmartPlay FPL",
    description:
      "Get AI-powered analysis of your FPL team with personalised recommendations.",
    images: ["/og-team.png"],
  },
  alternates: {
    canonical: "/my-team",
  },
};

export default function MyTeamLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
