"use client";

import { useState } from "react";
import { MessageSquare, Star, Send, X, CheckCircle2 } from "lucide-react";
import { trackFeedbackSubmission } from "@/lib/analytics";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FeedbackWidgetProps {
  teamId: string;
  gameweek: number;
}

const FEATURE_OPTIONS = [
  { value: "overall", label: "Overall Experience" },
  { value: "transfers", label: "Transfer Suggestions" },
  { value: "lineup", label: "Lineup Optimizer" },
  { value: "captain", label: "Captain Picks" },
  { value: "crowd_insights", label: "Crowd Insights" },
  { value: "ai_review", label: "AI Review" },
];

export default function FeedbackWidget({ teamId, gameweek }: FeedbackWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [feature, setFeature] = useState("overall");
  const [comment, setComment] = useState("");
  const [nps, setNps] = useState<number | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (rating === 0) {
      setError("Please select a rating");
      return;
    }

    setIsSubmitting(true);
    setError("");

    try {
      const apiBase = API_BASE.endsWith("/api") ? API_BASE : `${API_BASE}/api`;
      const res = await fetch(`${apiBase}/feedback/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          team_id: parseInt(teamId),
          gameweek,
          feature_type: feature,
          rating,
          would_recommend: nps,
          comment: comment.trim() || null,
          followed_advice: null,
        }),
      });

      if (res.ok) {
        setSubmitted(true);

        // Track feedback submission to Google Analytics
        const featureLabel = FEATURE_OPTIONS.find(opt => opt.value === feature)?.label || feature;
        trackFeedbackSubmission(
          featureLabel,
          rating,
          parseInt(teamId),
          gameweek,
          {
            wouldRecommend: nps ?? undefined,
            hasComment: !!comment.trim(),
            followedAdvice: undefined
          }
        );

        setTimeout(() => {
          setIsOpen(false);
          // Reset form after closing
          setTimeout(() => {
            setSubmitted(false);
            setRating(0);
            setFeature("overall");
            setComment("");
            setNps(null);
          }, 300);
        }, 2000);
      } else {
        setError("Failed to submit feedback. Please try again.");
      }
    } catch {
      setError("Connection error. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-red-500 to-rose-600 text-white rounded-full shadow-lg shadow-red-200 hover:shadow-xl hover:scale-105 transition-all duration-200 animate-pulse"
      >
        <MessageSquare className="w-5 h-5" />
        <span className="font-medium">Feedback</span>
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-80 sm:w-96 bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden animate-in slide-in-from-bottom-4 duration-300">
      {/* Header */}
      <div className="px-4 py-3 bg-gradient-to-r from-violet-600 to-purple-600 flex items-center justify-between">
        <div className="flex items-center gap-2 text-white">
          <MessageSquare className="w-5 h-5" />
          <span className="font-semibold">Share Your Feedback</span>
        </div>
        <button
          onClick={() => setIsOpen(false)}
          className="text-white/80 hover:text-white transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {submitted ? (
        <div className="p-8 text-center">
          <div className="w-16 h-16 mx-auto mb-4 bg-green-100 rounded-full flex items-center justify-center">
            <CheckCircle2 className="w-8 h-8 text-green-600" />
          </div>
          <h3 className="text-lg font-semibold text-slate-800 mb-2">Thank You!</h3>
          <p className="text-slate-500 text-sm">Your feedback helps us improve SmartPlayFPL.</p>
        </div>
      ) : (
        <div className="p-4 space-y-4">
          {/* Feature Select */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              What are you rating?
            </label>
            <select
              value={feature}
              onChange={(e) => setFeature(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-slate-700 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent"
            >
              {FEATURE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Star Rating */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              How would you rate it?
            </label>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onClick={() => setRating(star)}
                  onMouseEnter={() => setHoverRating(star)}
                  onMouseLeave={() => setHoverRating(0)}
                  className="p-1 transition-transform hover:scale-110"
                >
                  <Star
                    className={`w-8 h-8 transition-colors ${
                      star <= (hoverRating || rating)
                        ? "fill-yellow-400 text-yellow-400"
                        : "text-slate-300"
                    }`}
                  />
                </button>
              ))}
              {rating > 0 && (
                <span className="ml-2 text-sm text-slate-500">
                  {rating === 5 ? "Excellent!" : rating === 4 ? "Good" : rating === 3 ? "Okay" : rating === 2 ? "Poor" : "Bad"}
                </span>
              )}
            </div>
          </div>

          {/* NPS Score (optional) */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              How likely to recommend? <span className="text-slate-400 font-normal">(optional)</span>
            </label>
            <div className="flex items-center gap-1">
              {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((score) => (
                <button
                  key={score}
                  onClick={() => setNps(nps === score ? null : score)}
                  className={`w-7 h-7 text-xs font-medium rounded transition-colors ${
                    nps === score
                      ? score >= 9
                        ? "bg-green-500 text-white"
                        : score >= 7
                        ? "bg-yellow-500 text-white"
                        : "bg-red-500 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {score}
                </button>
              ))}
            </div>
          </div>

          {/* Comment */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              Any comments? <span className="text-slate-400 font-normal">(optional)</span>
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Tell us what you think..."
              rows={3}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-slate-700 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent resize-none"
              maxLength={500}
            />
          </div>

          {/* Error */}
          {error && (
            <p className="text-sm text-red-500">{error}</p>
          )}

          {/* Submit Button */}
          <button
            onClick={handleSubmit}
            disabled={isSubmitting || rating === 0}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-violet-600 to-purple-600 text-white font-medium rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Submitting...
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                Submit Feedback
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
