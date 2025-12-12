"use client";

import Link from "next/link";
import { GraduationCap, Linkedin, FileText } from "lucide-react";

export default function Footer() {
  return (
    <footer className="py-6 border-t border-slate-200 bg-white/50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex flex-col items-center gap-3">
          {/* Developer Info */}
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="w-9 h-9 sm:w-10 sm:h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center shadow-md">
              <GraduationCap className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <p className="text-xs sm:text-sm font-semibold text-slate-700">Qazybek Beken</p>
                <a
                  href="https://www.linkedin.com/in/qazybek-beken/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-700 transition-colors"
                  title="LinkedIn Profile"
                >
                  <Linkedin className="w-4 h-4" />
                </a>
              </div>
              <p className="text-[10px] sm:text-xs text-slate-500">UC Berkeley · School of Information</p>
            </div>
          </div>

          {/* Links and Tech Stack */}
          <div className="flex items-center gap-4 text-[10px] sm:text-xs text-slate-400">
            <Link
              href="/datasheet"
              className="flex items-center gap-1 hover:text-slate-600 transition-colors"
            >
              <FileText className="w-3 h-3" />
              <span>Datasheet</span>
            </Link>
            <span>·</span>
            <span>SmartPlay FPL</span>
            <span>·</span>
            <span>Built with Next.js · FastAPI · AI</span>
          </div>
        </div>
      </div>
    </footer>
  );
}

