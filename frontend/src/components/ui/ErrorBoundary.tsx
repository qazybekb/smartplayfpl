"use client";

import { Component, ReactNode } from "react";
import Link from "next/link";
import { AlertCircle, RefreshCw, Home, ArrowLeft, Bug, WifiOff } from "lucide-react";
import { cn } from "@/lib/utils";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ errorInfo });
    this.props.onError?.(error, errorInfo);
    // Log to error tracking service in production
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <ErrorDisplay
          error={this.state.error}
          onRetry={() => this.setState({ hasError: false, error: null, errorInfo: null })}
        />
      );
    }

    return this.props.children;
  }
}

// Reusable error display component
interface ErrorDisplayProps {
  error?: Error | null;
  title?: string;
  description?: string;
  variant?: "full-page" | "inline" | "card";
  showRetry?: boolean;
  showHome?: boolean;
  showBack?: boolean;
  onRetry?: () => void;
  backHref?: string;
  className?: string;
}

export function ErrorDisplay({
  error,
  title,
  description,
  variant = "card",
  showRetry = true,
  showHome = true,
  showBack = false,
  onRetry,
  backHref = "/",
  className,
}: ErrorDisplayProps) {
  // Determine error type for better messaging
  const isNetworkError = error?.message?.toLowerCase().includes("network") ||
    error?.message?.toLowerCase().includes("fetch") ||
    error?.message?.toLowerCase().includes("failed to load");

  const isNotFoundError = error?.message?.toLowerCase().includes("404") ||
    error?.message?.toLowerCase().includes("not found");

  const defaultTitle = isNotFoundError
    ? "Not Found"
    : isNetworkError
      ? "Connection Error"
      : "Something went wrong";

  const defaultDescription = isNotFoundError
    ? "The page or resource you're looking for doesn't exist."
    : isNetworkError
      ? "Please check your internet connection and try again."
      : "An unexpected error occurred. Please try again.";

  const Icon = isNetworkError ? WifiOff : isNotFoundError ? Bug : AlertCircle;
  const iconColor = isNotFoundError ? "text-amber-500" : "text-red-500";
  const iconBg = isNotFoundError ? "bg-amber-100" : "bg-red-100";

  const containerClasses = cn(
    {
      "min-h-screen bg-gradient-to-br from-slate-50 via-white to-red-50 flex items-center justify-center p-4":
        variant === "full-page",
      "py-8": variant === "inline",
      "bg-white rounded-2xl border border-slate-200 shadow-lg p-8": variant === "card",
    },
    className
  );

  const content = (
    <div className={cn(
      "text-center",
      variant === "full-page" && "max-w-md mx-auto"
    )}>
      <div className={cn(
        "w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4",
        iconBg
      )}>
        <Icon className={cn("w-8 h-8", iconColor)} />
      </div>

      <h2 className="text-xl font-bold text-slate-800 mb-2">
        {title || defaultTitle}
      </h2>

      <p className="text-slate-600 mb-6 max-w-sm mx-auto">
        {description || defaultDescription}
      </p>

      {/* Error details in development */}
      {process.env.NODE_ENV === "development" && error && (
        <details className="mb-6 text-left bg-slate-50 rounded-lg p-4 text-sm">
          <summary className="cursor-pointer text-slate-500 font-medium mb-2">
            Error Details
          </summary>
          <pre className="text-xs text-red-600 overflow-auto whitespace-pre-wrap">
            {error.message}
            {error.stack && `\n\n${error.stack}`}
          </pre>
        </details>
      )}

      <div className="flex items-center justify-center gap-3 flex-wrap">
        {showBack && (
          <Link
            href={backHref}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-slate-100 text-slate-700 font-medium rounded-xl hover:bg-slate-200 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Go Back
          </Link>
        )}

        {showRetry && onRetry && (
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-emerald-600 text-white font-medium rounded-xl hover:bg-emerald-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>
        )}

        {showHome && (
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-slate-100 text-slate-700 font-medium rounded-xl hover:bg-slate-200 transition-colors"
          >
            <Home className="w-4 h-4" />
            Home
          </Link>
        )}
      </div>
    </div>
  );

  return <div className={containerClasses}>{content}</div>;
}

// API error handler hook
export function useApiError() {
  const handleApiError = (error: unknown): string => {
    if (error instanceof Error) {
      // Network errors
      if (error.message.includes("fetch")) {
        return "Unable to connect to the server. Please check your connection.";
      }
      // Timeout
      if (error.message.includes("timeout")) {
        return "The request timed out. Please try again.";
      }
      // Rate limiting
      if (error.message.includes("429") || error.message.includes("rate")) {
        return "Too many requests. Please wait a moment and try again.";
      }
      // Not found
      if (error.message.includes("404")) {
        return "The requested resource was not found.";
      }
      // Server error
      if (error.message.includes("500") || error.message.includes("server")) {
        return "Server error. Our team has been notified.";
      }
      return error.message;
    }
    return "An unexpected error occurred.";
  };

  return { handleApiError };
}

// Empty state component
interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick?: () => void;
    href?: string;
  };
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className
}: EmptyStateProps) {
  return (
    <div className={cn("text-center py-12", className)}>
      {icon && (
        <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-semibold text-slate-800 mb-2">{title}</h3>
      {description && (
        <p className="text-slate-500 mb-6 max-w-sm mx-auto">{description}</p>
      )}
      {action && (
        action.href ? (
          <Link
            href={action.href}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-emerald-600 text-white font-medium rounded-xl hover:bg-emerald-700 transition-colors"
          >
            {action.label}
          </Link>
        ) : (
          <button
            onClick={action.onClick}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-emerald-600 text-white font-medium rounded-xl hover:bg-emerald-700 transition-colors"
          >
            {action.label}
          </button>
        )
      )}
    </div>
  );
}
