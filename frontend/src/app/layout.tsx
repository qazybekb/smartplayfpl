import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import "./globals.css";
import ErrorBoundaryWrapper from "@/components/ErrorBoundaryWrapper";
import AnalyticsProvider from "@/components/AnalyticsProvider";
import Footer from "@/components/Footer";

// Site configuration for SEO
const siteConfig = {
  name: "SmartPlay FPL",
  url: "https://smartplayfpl.com",
  description: "AI-powered Fantasy Premier League assistant. Get personalised transfer recommendations, captain picks, squad analysis, and chip strategy with explanations for every decision.",
  keywords: [
    "FPL",
    "Fantasy Premier League",
    "FPL AI",
    "FPL assistant",
    "FPL transfer tips",
    "FPL captain picks",
    "Fantasy football AI",
    "FPL predictions",
    "FPL analysis",
    "FPL squad builder",
    "FPL team analyser",
    "FPL differential",
    "FPL machine learning",
    "SmartPlay FPL",
    "FPL knowledge graph",
    "FPL optimisation",
    "Fantasy Premier League tips",
    "FPL GW analysis",
    "FPL wildcard strategy",
    "FPL chip strategy",
  ],
  author: "SmartPlay FPL Team",
  creator: "UC Berkeley Students",
  publisher: "SmartPlay FPL",
  twitterHandle: "@SmartPlayFPL",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#10b981" },
    { media: "(prefers-color-scheme: dark)", color: "#059669" },
  ],
};

export const metadata: Metadata = {
  // Basic metadata
  title: {
    default: "SmartPlay FPL - AI-Powered Fantasy Premier League Assistant",
    template: "%s | SmartPlay FPL",
  },
  description: siteConfig.description,
  keywords: siteConfig.keywords,
  authors: [{ name: siteConfig.author }],
  creator: siteConfig.creator,
  publisher: siteConfig.publisher,

  // Canonical URL
  metadataBase: new URL(siteConfig.url),
  alternates: {
    canonical: "/",
  },

  // Robots
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },

  // Open Graph
  openGraph: {
    type: "website",
    locale: "en_GB",
    url: siteConfig.url,
    siteName: siteConfig.name,
    title: "SmartPlay FPL - AI-Powered Fantasy Premier League Assistant",
    description: siteConfig.description,
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "SmartPlay FPL - AI-powered FPL analysis",
        type: "image/png",
      },
    ],
  },

  // Twitter Card
  twitter: {
    card: "summary_large_image",
    site: siteConfig.twitterHandle,
    creator: siteConfig.twitterHandle,
    title: "SmartPlay FPL - AI-Powered Fantasy Premier League Assistant",
    description: siteConfig.description,
    images: ["/og-image.png"],
  },

  // Icons
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
    ],
    apple: [
      { url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
    other: [
      {
        rel: "mask-icon",
        url: "/safari-pinned-tab.svg",
        color: "#10b981",
      },
    ],
  },

  // Manifest
  manifest: "/site.webmanifest",

  // App-specific metadata
  applicationName: siteConfig.name,
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: siteConfig.name,
  },
  formatDetection: {
    telephone: false,
  },

  // Verification (add your actual verification codes)
  verification: {
    google: "your-google-verification-code",
    // yandex: "your-yandex-verification-code",
    // bing: "your-bing-verification-code",
  },

  // Category for better classification
  category: "sports",

  // Other metadata
  other: {
    "msapplication-TileColor": "#10b981",
    "theme-color": "#10b981",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" dir="ltr">
      <head>
        {/* Google Analytics 4 */}
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-6RKKN9VH99"></script>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', 'G-6RKKN9VH99', {
                page_path: window.location.pathname,
                anonymize_ip: true
              });
            `,
          }}
        />
        {/* Preconnect to external domains for performance */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="preconnect" href="https://www.googletagmanager.com" />

        {/* DNS prefetch for API */}
        <link rel="dns-prefetch" href="https://smartplayfpl-500287436620.europe-west1.run.app" />

        {/* Structured Data - Organization */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "WebSite",
              name: "SmartPlay FPL",
              alternateName: "SmartPlay Fantasy Premier League",
              url: "https://smartplayfpl.com",
              description: "AI-powered Fantasy Premier League assistant with transfer recommendations, captain picks, squad analysis, and chip strategy.",
              publisher: {
                "@type": "Organization",
                name: "SmartPlay FPL",
                logo: {
                  "@type": "ImageObject",
                  url: "https://smartplayfpl.com/logo.png",
                },
              },
              potentialAction: {
                "@type": "SearchAction",
                target: {
                  "@type": "EntryPoint",
                  urlTemplate: "https://smartplayfpl.com/players?search={search_term_string}",
                },
                "query-input": "required name=search_term_string",
              },
            }),
          }}
        />

        {/* Structured Data - Software Application */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "SoftwareApplication",
              name: "SmartPlay FPL",
              applicationCategory: "SportsApplication",
              operatingSystem: "Web Browser",
              offers: {
                "@type": "Offer",
                price: "0",
                priceCurrency: "USD",
              },
              description: "AI-powered Fantasy Premier League assistant.",
              featureList: [
                "AI-powered transfer recommendations",
                "Captain pick analysis",
                "Squad optimisation",
                "Crowd insights from Top 10k managers",
                "Machine learning predictions",
              ],
            }),
          }}
        />
      </head>
      <body className="antialiased min-h-screen bg-slate-50 flex flex-col" suppressHydrationWarning>
        <ErrorBoundaryWrapper>
          <Suspense fallback={null}>
            <AnalyticsProvider>
              <main className="flex-1">
                {children}
              </main>
              <Footer />
            </AnalyticsProvider>
          </Suspense>
        </ErrorBoundaryWrapper>
      </body>
    </html>
  );
}

