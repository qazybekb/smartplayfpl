"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Brain,
  Menu,
  X,
  Home,
  Users,
  Wand2,
  BarChart3,
  Search,
  ChevronRight,
  ArrowLeft,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface AppHeaderProps {
  variant?: "default" | "transparent" | "colored";
  showBack?: boolean;
  backHref?: string;
  backLabel?: string;
  title?: string;
  subtitle?: string;
  rightContent?: React.ReactNode;
}

const NAV_ITEMS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/players", label: "Players", icon: Search },
  { href: "/build", label: "Build Squad", icon: Wand2 },
  { href: "/model", label: "AI Model", icon: BarChart3 },
];

export function AppHeader({
  variant = "default",
  showBack = false,
  backHref = "/",
  backLabel = "Back",
  title,
  subtitle,
  rightContent,
}: AppHeaderProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const pathname = usePathname();

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  const headerClasses = cn(
    "sticky top-0 z-50 transition-all duration-300",
    {
      "bg-white/95 backdrop-blur-xl shadow-sm border-b border-slate-200/60": variant === "default",
      "bg-transparent": variant === "transparent",
      "bg-gradient-to-r from-emerald-600 to-teal-600 text-white": variant === "colored",
    }
  );

  const linkClasses = cn(
    "font-medium transition-colors",
    {
      "text-slate-600 hover:text-emerald-600": variant !== "colored",
      "text-white/80 hover:text-white": variant === "colored",
    }
  );

  const activeLinkClasses = cn({
    "text-emerald-600": variant !== "colored",
    "text-white": variant === "colored",
  });

  return (
    <header className={headerClasses}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-14 sm:h-16">
          {/* Left Section */}
          <div className="flex items-center gap-3">
            {showBack ? (
              <Link
                href={backHref}
                className={cn(
                  "inline-flex items-center gap-2 transition-colors",
                  variant === "colored"
                    ? "text-white/80 hover:text-white"
                    : "text-slate-600 hover:text-slate-800"
                )}
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="text-sm font-medium hidden sm:inline">{backLabel}</span>
              </Link>
            ) : (
              <Link href="/" className="flex items-center gap-2 sm:gap-3">
                <div className={cn(
                  "w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center shadow-lg",
                  variant === "colored"
                    ? "bg-white/20"
                    : "bg-gradient-to-br from-emerald-500 to-teal-600 shadow-emerald-500/25"
                )}>
                  <Brain className={cn(
                    "w-5 h-5",
                    variant === "colored" ? "text-white" : "text-white"
                  )} />
                </div>
                <span className={cn(
                  "text-lg sm:text-xl font-bold",
                  variant === "colored" ? "text-white" : "text-slate-900"
                )}>
                  Smart<span className={variant === "colored" ? "text-white" : "text-emerald-600"}>Play</span>
                </span>
              </Link>
            )}

            {/* Title for inner pages */}
            {title && (
              <div className="hidden sm:flex items-center gap-2 ml-4 pl-4 border-l border-slate-200/60">
                <div>
                  <h1 className={cn(
                    "font-semibold",
                    variant === "colored" ? "text-white" : "text-slate-900"
                  )}>
                    {title}
                  </h1>
                  {subtitle && (
                    <p className={cn(
                      "text-xs",
                      variant === "colored" ? "text-white/70" : "text-slate-500"
                    )}>
                      {subtitle}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-1" role="navigation" aria-label="Main navigation">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "px-3 py-2 rounded-lg text-sm transition-colors",
                  isActive(item.href) ? activeLinkClasses : linkClasses,
                  isActive(item.href) && variant !== "colored" && "bg-emerald-50"
                )}
                aria-current={isActive(item.href) ? "page" : undefined}
              >
                {item.label}
              </Link>
            ))}
            {rightContent}
          </nav>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className={cn(
              "md:hidden p-2 rounded-lg transition-colors",
              variant === "colored"
                ? "hover:bg-white/10"
                : "hover:bg-slate-100"
            )}
            aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileMenuOpen}
            aria-controls="mobile-menu"
          >
            {mobileMenuOpen ? (
              <X className={cn("w-6 h-6", variant === "colored" ? "text-white" : "text-slate-700")} />
            ) : (
              <Menu className={cn("w-6 h-6", variant === "colored" ? "text-white" : "text-slate-700")} />
            )}
          </button>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <nav
            id="mobile-menu"
            className={cn(
              "md:hidden py-4 border-t space-y-1",
              variant === "colored" ? "border-white/20" : "border-slate-100"
            )}
            role="navigation"
            aria-label="Mobile navigation"
          >
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={cn(
                  "flex items-center gap-3 px-4 py-3 rounded-lg transition-colors",
                  isActive(item.href)
                    ? variant === "colored"
                      ? "bg-white/10 text-white"
                      : "bg-emerald-50 text-emerald-600"
                    : variant === "colored"
                      ? "text-white/80 hover:bg-white/10"
                      : "text-slate-700 hover:bg-slate-50"
                )}
                aria-current={isActive(item.href) ? "page" : undefined}
              >
                <item.icon className="w-5 h-5" />
                <span className="font-medium">{item.label}</span>
                <ChevronRight className="w-4 h-4 ml-auto opacity-50" />
              </Link>
            ))}
            {rightContent && (
              <div className="pt-3 border-t border-slate-100">
                {rightContent}
              </div>
            )}
          </nav>
        )}
      </div>
    </header>
  );
}

// Breadcrumb component
interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
  className?: string;
}

export function Breadcrumbs({ items, className }: BreadcrumbsProps) {
  return (
    <nav
      aria-label="Breadcrumb"
      className={cn("flex items-center gap-2 text-sm", className)}
    >
      {items.map((item, index) => (
        <span key={index} className="flex items-center gap-2">
          {index > 0 && (
            <ChevronRight className="w-4 h-4 text-slate-300" aria-hidden="true" />
          )}
          {item.href ? (
            <Link
              href={item.href}
              className="text-slate-500 hover:text-slate-700 transition-colors"
            >
              {item.label}
            </Link>
          ) : (
            <span className="text-slate-900 font-medium" aria-current="page">
              {item.label}
            </span>
          )}
        </span>
      ))}
    </nav>
  );
}
