"use client";

import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { getCurrentGameweek, type Gameweek } from "@/lib/api";

interface DeadlineCountdownProps {
  compact?: boolean;
}

interface TimeLeft {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  isUrgent: boolean;
}

export default function DeadlineCountdown({ compact = false }: DeadlineCountdownProps) {
  const [gameweek, setGameweek] = useState<Gameweek | null>(null);
  const [timeLeft, setTimeLeft] = useState<TimeLeft | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCurrentGameweek()
      .then(setGameweek)
      .catch(() => {}) // Silent fail
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!gameweek) return;

    const deadline = new Date(gameweek.deadline_time);

    const calculateTimeLeft = () => {
      const now = new Date();
      const diff = deadline.getTime() - now.getTime();

      if (diff <= 0) {
        return null;
      }

      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);
      const isUrgent = diff < 1000 * 60 * 60 * 24; // Less than 24 hours

      return { days, hours, minutes, seconds, isUrgent };
    };

    setTimeLeft(calculateTimeLeft());

    const timer = setInterval(() => {
      setTimeLeft(calculateTimeLeft());
    }, 1000);

    return () => clearInterval(timer);
  }, [gameweek]);

  if (loading) {
    return (
      <div className="bg-gradient-to-r from-violet-600 to-purple-600 rounded-xl px-4 py-3 shadow-lg animate-pulse">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-white/20 rounded-full" />
          <div className="flex-1">
            <div className="h-3 bg-white/20 rounded w-24 mb-2" />
            <div className="h-6 bg-white/20 rounded w-32" />
          </div>
        </div>
      </div>
    );
  }

  if (!gameweek) return null;

  // Deadline passed
  if (!timeLeft) {
    return (
      <div className="bg-gradient-to-r from-slate-700 to-slate-800 rounded-xl px-4 py-3 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-full bg-white/20">
            <Clock className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1">
            <p className="text-white/80 text-xs font-medium uppercase tracking-wide">
              {gameweek.name}
            </p>
            <p className="text-white font-semibold">Deadline Passed</p>
          </div>
        </div>
      </div>
    );
  }

  // Compact version (for header/nav)
  if (compact) {
    return (
      <div className={`rounded-lg px-3 py-2 ${
        timeLeft.isUrgent
          ? "bg-gradient-to-r from-red-600 to-rose-600"
          : "bg-gradient-to-r from-slate-700 to-slate-800"
      } shadow-md`}>
        <div className="flex items-center gap-2">
          <Clock className={`w-4 h-4 text-white ${timeLeft.isUrgent ? "animate-pulse" : ""}`} />
          <div className="text-white">
            <p className="text-[10px] font-medium uppercase tracking-wide opacity-90">
              {gameweek.name}
            </p>
            <p className="text-sm font-bold tabular-nums">
              {String(timeLeft.days).padStart(2, '0')}:
              {String(timeLeft.hours).padStart(2, '0')}:
              {String(timeLeft.minutes).padStart(2, '0')}:
              {String(timeLeft.seconds).padStart(2, '0')}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Full version
  return (
    <div className={`rounded-xl px-3 sm:px-6 py-3 sm:py-4 shadow-lg ${
      timeLeft.isUrgent
        ? "bg-gradient-to-r from-red-600 to-rose-600"
        : "bg-gradient-to-r from-slate-700 to-slate-800"
    }`}>
      <div className="flex flex-col sm:flex-row items-center sm:justify-between gap-3 sm:gap-0">
        <div className="flex items-center gap-2 sm:gap-4 w-full sm:w-auto justify-center sm:justify-start">
          <div className={`p-2 sm:p-3 rounded-full ${timeLeft.isUrgent ? "bg-red-500/30" : "bg-slate-600/50"}`}>
            <Clock className={`w-4 h-4 sm:w-6 sm:h-6 text-white ${timeLeft.isUrgent ? "animate-pulse" : ""}`} />
          </div>
          <div className="text-center sm:text-left">
            <p className="text-white/90 text-[10px] sm:text-xs font-semibold uppercase tracking-wide mb-0.5 sm:mb-1">
              {gameweek.name} Deadline
            </p>
            <p className="text-white/80 text-xs sm:text-sm">
              {new Date(gameweek.deadline_time).toLocaleDateString('en-GB', {
                weekday: 'short',
                day: 'numeric',
                month: 'short',
                hour: '2-digit',
                minute: '2-digit'
              })}
            </p>
          </div>
        </div>
        <div className="text-center">
          <p className="text-white/90 text-[10px] sm:text-xs font-semibold uppercase tracking-wide mb-1 hidden sm:block">
            Time Remaining
          </p>
          <div className="flex items-center gap-1 sm:gap-2">
            <div className="text-center">
              <p className="text-white text-xl sm:text-3xl font-bold tabular-nums">
                {String(timeLeft.days).padStart(2, '0')}
              </p>
              <p className="text-white/70 text-[8px] sm:text-[10px] font-medium uppercase">Days</p>
            </div>
            <span className="text-white text-lg sm:text-2xl font-bold">:</span>
            <div className="text-center">
              <p className="text-white text-xl sm:text-3xl font-bold tabular-nums">
                {String(timeLeft.hours).padStart(2, '0')}
              </p>
              <p className="text-white/70 text-[8px] sm:text-[10px] font-medium uppercase">Hrs</p>
            </div>
            <span className="text-white text-lg sm:text-2xl font-bold">:</span>
            <div className="text-center">
              <p className="text-white text-xl sm:text-3xl font-bold tabular-nums">
                {String(timeLeft.minutes).padStart(2, '0')}
              </p>
              <p className="text-white/70 text-[8px] sm:text-[10px] font-medium uppercase">Min</p>
            </div>
            <span className="text-white text-lg sm:text-2xl font-bold">:</span>
            <div className="text-center">
              <p className="text-white text-xl sm:text-3xl font-bold tabular-nums">
                {String(timeLeft.seconds).padStart(2, '0')}
              </p>
              <p className="text-white/70 text-[8px] sm:text-[10px] font-medium uppercase">Sec</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
