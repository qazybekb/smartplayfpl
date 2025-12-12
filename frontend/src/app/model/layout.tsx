import { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Model - Machine Learning for FPL Predictions",
  description:
    "Learn about SmartPlay's AI prediction models for Fantasy Premier League. Custom machine learning models trained on historical FPL data predict player points and playing time with high accuracy.",
  keywords: [
    "FPL AI model",
    "FPL machine learning",
    "FPL predictions",
    "Fantasy Premier League AI",
    "FPL point predictions",
    "FPL playing time predictor",
    "FPL data science",
    "SmartPlay Score formula",
    "FPL algorithm",
    "FPL statistics",
  ],
  openGraph: {
    title: "AI Model - Machine Learning for FPL | SmartPlay FPL",
    description:
      "Machine learning models for Fantasy Premier League predictions. Trained on historical data to predict player points and playing time.",
    type: "website",
    url: "https://smartplayfpl.com/model",
    images: [
      {
        url: "/og-model.png",
        width: 1200,
        height: 630,
        alt: "SmartPlay FPL AI Model",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Model - Machine Learning for FPL | SmartPlay FPL",
    description:
      "Learn about our ML models for FPL predictions and SmartPlay Scores.",
    images: ["/og-model.png"],
  },
  alternates: {
    canonical: "/model",
  },
};

export default function ModelLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
