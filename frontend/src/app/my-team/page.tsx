"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Redirect /my-team to the landing page
 * The main entry point for team analysis is now on the landing page
 * with a unified FPL ID input and recent teams feature
 */
export default function MyTeamRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to landing page
    router.replace("/");
  }, [router]);

  // Show minimal loading state during redirect
  return (
    <div className="bg-gradient-to-br from-slate-50 via-white to-emerald-50 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin w-8 h-8 border-3 border-emerald-200 border-t-emerald-600 rounded-full mx-auto mb-3" />
        <p className="text-slate-500 text-sm">Redirecting...</p>
      </div>
    </div>
  );
}
