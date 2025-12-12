"use client";

import { useEffect, useRef, useCallback } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import Script from "next/script";
import {
  initGA,
  trackPageView,
  trackScrollDepth,
  trackTimeOnPage,
  startNewSession,
  trackWebVitals,
} from "@/lib/analytics";

const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "G-6RKKN9VH99";

interface AnalyticsProviderProps {
  children: React.ReactNode;
}

export default function AnalyticsProvider({ children }: AnalyticsProviderProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const sessionStarted = useRef(false);
  const pageStartTime = useRef<number>(Date.now());
  const scrollDepthsTracked = useRef<Set<number>>(new Set());

  // Initialize GA and start session on first load
  useEffect(() => {
    if (!sessionStarted.current) {
      initGA();
      startNewSession();
      sessionStarted.current = true;
    }
  }, []);

  // Track page views on route change
  useEffect(() => {
    const url = pathname + (searchParams?.toString() ? `?${searchParams.toString()}` : "");
    trackPageView(url, document.title);

    // Reset page metrics
    pageStartTime.current = Date.now();
    scrollDepthsTracked.current = new Set();
  }, [pathname, searchParams]);

  // Track scroll depth
  const handleScroll = useCallback(() => {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const scrollPercent = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;

    const depths = [25, 50, 75, 100] as const;
    for (const depth of depths) {
      if (scrollPercent >= depth && !scrollDepthsTracked.current.has(depth)) {
        scrollDepthsTracked.current.add(depth);
        trackScrollDepth(depth, pathname);
      }
    }
  }, [pathname]);

  // Track time on page before leaving
  const handleBeforeUnload = useCallback(() => {
    const timeOnPage = Math.round((Date.now() - pageStartTime.current) / 1000);
    trackTimeOnPage(pathname, timeOnPage);
  }, [pathname]);

  // Set up scroll and beforeunload listeners
  useEffect(() => {
    window.addEventListener("scroll", handleScroll, { passive: true });
    window.addEventListener("beforeunload", handleBeforeUnload);

    return () => {
      window.removeEventListener("scroll", handleScroll);
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [handleScroll, handleBeforeUnload]);

  // Track Web Vitals
  useEffect(() => {
    // Dynamic import to avoid SSR issues
    import("web-vitals").then(({ onCLS, onINP, onFCP, onLCP, onTTFB }) => {
      const reportMetric = (metric: { name: string; value: number; rating: "good" | "needs-improvement" | "poor"; id: string }) => {
        trackWebVitals(metric);
      };

      onCLS(reportMetric);
      onINP(reportMetric);
      onFCP(reportMetric);
      onLCP(reportMetric);
      onTTFB(reportMetric);
    }).catch(() => {
      // web-vitals not installed, skip
    });
  }, []);

  return (
    <>
      {/* Google Analytics Scripts */}
      {GA_MEASUREMENT_ID && (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`}
            strategy="afterInteractive"
          />
          <Script id="ga-config" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', '${GA_MEASUREMENT_ID}', {
                page_path: window.location.pathname,
                anonymize_ip: true,
              });
            `}
          </Script>
        </>
      )}
      {children}
    </>
  );
}
