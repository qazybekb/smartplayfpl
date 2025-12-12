import { Metadata } from "next";

export const metadata: Metadata = {
  title: "FPL Player Database - Search 750+ Players",
  description:
    "Search and compare 750+ Fantasy Premier League players. Filter by position, team, price, form, and SmartPlay Score. Find the best differentials, value picks, and transfers for your FPL team.",
  keywords: [
    "FPL players",
    "FPL player search",
    "Fantasy Premier League players",
    "FPL database",
    "FPL player stats",
    "FPL compare players",
    "FPL differentials",
    "FPL value picks",
    "FPL player form",
    "FPL player ownership",
  ],
  openGraph: {
    title: "FPL Player Database - Search 750+ Players | SmartPlay FPL",
    description:
      "Search and compare 750+ Fantasy Premier League players with advanced filters and SmartPlay Scores.",
    type: "website",
    url: "https://smartplayfpl.com/players",
    images: [
      {
        url: "/og-players.png",
        width: 1200,
        height: 630,
        alt: "SmartPlay FPL Player Database",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "FPL Player Database - Search 750+ Players | SmartPlay FPL",
    description:
      "Search and compare 750+ Fantasy Premier League players with advanced filters.",
    images: ["/og-players.png"],
  },
  alternates: {
    canonical: "/players",
  },
};

export default function PlayersLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
