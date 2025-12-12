"use client";

import { ReactNode } from "react";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

interface ErrorBoundaryWrapperProps {
  children: ReactNode;
}

export default function ErrorBoundaryWrapper({ children }: ErrorBoundaryWrapperProps) {
  return (
    <ErrorBoundary
      onError={(error, errorInfo) => {
        // Log to error tracking service in production
        if (process.env.NODE_ENV === "production") {
          // Could send to Sentry, LogRocket, etc.
          console.error("Application error:", error, errorInfo);
        }
      }}
    >
      {children}
    </ErrorBoundary>
  );
}
