'use client';

import { useState, useEffect, useCallback } from 'react';

interface FeatureRanking {
  feature_type: string;
  avg_rating: number;
  total_ratings: number;
  rating_distribution: Record<string, number>;
}

interface DashboardData {
  unique_users: number;
  total_submissions: number;
  avg_overall_rating: number;
  avg_nps: number | null;
  feature_rankings: FeatureRanking[];
  nps_promoters: number;
  nps_passives: number;
  nps_detractors: number;
  followed_yes: number;
  followed_no: number;
  followed_partially: number;
}

interface CommentEntry {
  id: number;
  team_id: number;
  gameweek: number;
  feature_type: string;
  rating: number;
  comment: string;
  created_at: string;
}

interface CommentsResponse {
  comments: CommentEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function AdminFeedbackPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [authError, setAuthError] = useState('');
  const [loading, setLoading] = useState(false);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [comments, setComments] = useState<CommentsResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'rankings' | 'comments'>('overview');
  const [commentsPage, setCommentsPage] = useState(1);
  const [filterFeature, setFilterFeature] = useState('');
  const [timeFilter, setTimeFilter] = useState(30); // days

  const fetchData = useCallback(async (adminPassword: string) => {
    setLoading(true);
    try {
      const apiBase = API_BASE.endsWith('/api') ? API_BASE : `${API_BASE}/api`;

      // Fetch dashboard data
      const dashRes = await fetch(`${apiBase}/feedback/admin/dashboard?days=${timeFilter}`, {
        headers: { 'X-Admin-Password': adminPassword },
      });

      if (dashRes.status === 401) {
        setIsAuthenticated(false);
        setAuthError('Session expired. Please log in again.');
        sessionStorage.removeItem('admin_password');
        return;
      }

      if (dashRes.ok) {
        const dashData = await dashRes.json();
        setDashboard(dashData);
      }

      // Fetch comments
      const commentsRes = await fetch(
        `${apiBase}/feedback/admin/comments?page=${commentsPage}&page_size=20${filterFeature ? `&feature_type=${encodeURIComponent(filterFeature)}` : ''}`,
        {
          headers: { 'X-Admin-Password': adminPassword },
        }
      );

      if (commentsRes.ok) {
        const commentsData = await commentsRes.json();
        setComments(commentsData);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  }, [commentsPage, filterFeature, timeFilter]);

  useEffect(() => {
    const storedPassword = sessionStorage.getItem('admin_password');
    if (storedPassword) {
      setPassword(storedPassword);
      setIsAuthenticated(true);
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated && password) {
      fetchData(password);
    }
  }, [isAuthenticated, password, commentsPage, filterFeature, timeFilter, fetchData]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    setLoading(true);

    try {
      const apiBase = API_BASE.endsWith('/api') ? API_BASE : `${API_BASE}/api`;
      const res = await fetch(`${apiBase}/feedback/admin/dashboard?days=1`, {
        headers: { 'X-Admin-Password': password },
      });

      if (res.status === 401) {
        setAuthError('Invalid password');
        setLoading(false);
        return;
      }

      if (res.ok) {
        sessionStorage.setItem('admin_password', password);
        setIsAuthenticated(true);
      }
    } catch (error) {
      setAuthError('Connection error. Is the backend running?');
      console.error('Auth error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem('admin_password');
    setIsAuthenticated(false);
    setPassword('');
    setDashboard(null);
    setComments(null);
  };

  const renderStars = (rating: number) => {
    return Array(5)
      .fill(0)
      .map((_, i) => (
        <span key={i} className={i < rating ? 'text-yellow-400' : 'text-gray-600'}>
          ★
        </span>
      ));
  };

  const getRatingColor = (rating: number) => {
    if (rating >= 4.5) return 'text-green-400';
    if (rating >= 3.5) return 'text-yellow-400';
    if (rating >= 2.5) return 'text-orange-400';
    return 'text-red-400';
  };

  // Login screen
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#0f0f23] flex items-center justify-center p-4">
        <div className="bg-[#1a1a2e] rounded-lg p-8 w-full max-w-md border border-gray-800">
          <h1 className="text-2xl font-bold text-white mb-6 text-center">
            Admin Login
          </h1>
          <form onSubmit={handleLogin}>
            <div className="mb-4">
              <label className="block text-gray-400 mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-[#0f0f23] text-white border border-gray-700 rounded px-4 py-2 focus:outline-none focus:border-purple-500"
                placeholder="Enter admin password"
                autoFocus
              />
            </div>
            {authError && (
              <p className="text-red-400 text-sm mb-4">{authError}</p>
            )}
            <button
              type="submit"
              disabled={loading || !password}
              className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 text-white font-medium py-2 rounded transition-colors"
            >
              {loading ? 'Authenticating...' : 'Login'}
            </button>
          </form>
          <p className="text-gray-500 text-xs mt-4 text-center">
            Default password: smartplay2024
          </p>
        </div>
      </div>
    );
  }

  // Dashboard
  return (
    <div className="min-h-screen bg-[#0f0f23] text-white p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold">Feedback Dashboard</h1>
          <div className="flex items-center gap-4">
            <select
              value={timeFilter}
              onChange={(e) => {
                setTimeFilter(Number(e.target.value));
                setCommentsPage(1);
              }}
              className="bg-[#1a1a2e] border border-gray-700 rounded px-3 py-1.5 text-sm text-white"
            >
              <option value={10}>Last 10 days</option>
              <option value={20}>Last 20 days</option>
              <option value={30}>Last 30 days</option>
              <option value={60}>Last 60 days</option>
              <option value={365}>All time</option>
            </select>
            <button
              onClick={handleLogout}
              className="text-gray-400 hover:text-white text-sm"
            >
              Logout
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="max-w-7xl mx-auto mb-6">
        <div className="flex gap-4 border-b border-gray-800">
          <button
            onClick={() => setActiveTab('overview')}
            className={`pb-2 px-4 ${
              activeTab === 'overview'
                ? 'border-b-2 border-purple-500 text-white'
                : 'text-gray-400'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('rankings')}
            className={`pb-2 px-4 ${
              activeTab === 'rankings'
                ? 'border-b-2 border-purple-500 text-white'
                : 'text-gray-400'
            }`}
          >
            Feature Rankings
          </button>
          <button
            onClick={() => setActiveTab('comments')}
            className={`pb-2 px-4 ${
              activeTab === 'comments'
                ? 'border-b-2 border-purple-500 text-white'
                : 'text-gray-400'
            }`}
          >
            Comments
          </button>
        </div>
      </div>

      {loading && !dashboard ? (
        <div className="text-center text-gray-400 py-12">Loading...</div>
      ) : activeTab === 'overview' && dashboard ? (
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-[#1a1a2e] rounded-lg p-6 border border-gray-800">
              <div className="text-gray-400 text-sm">Unique Users</div>
              <div className="text-3xl font-bold mt-2 text-blue-400">{dashboard.unique_users}</div>
            </div>
            <div className="bg-[#1a1a2e] rounded-lg p-6 border border-gray-800">
              <div className="text-gray-400 text-sm">Average Rating</div>
              <div className={`text-3xl font-bold mt-2 ${getRatingColor(dashboard.avg_overall_rating)}`}>
                {dashboard.avg_overall_rating.toFixed(1)}/5
              </div>
            </div>
            <div className="bg-[#1a1a2e] rounded-lg p-6 border border-gray-800">
              <div className="text-gray-400 text-sm">Avg NPS Score</div>
              <div className="text-3xl font-bold mt-2">
                {dashboard.avg_nps !== null ? dashboard.avg_nps.toFixed(1) : 'N/A'}
              </div>
            </div>
          </div>

          {/* NPS Breakdown */}
          <div className="bg-[#1a1a2e] rounded-lg p-6 border border-gray-800">
            <h2 className="text-xl font-bold mb-4">NPS Breakdown</h2>
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-4xl font-bold text-green-400">{dashboard.nps_promoters}</div>
                <div className="text-sm text-gray-400 mt-1">Promoters (9-10)</div>
              </div>
              <div className="text-center">
                <div className="text-4xl font-bold text-yellow-400">{dashboard.nps_passives}</div>
                <div className="text-sm text-gray-400 mt-1">Passives (7-8)</div>
              </div>
              <div className="text-center">
                <div className="text-4xl font-bold text-red-400">{dashboard.nps_detractors}</div>
                <div className="text-sm text-gray-400 mt-1">Detractors (0-6)</div>
              </div>
              <div className="text-center border-l border-gray-700 pl-4">
                <div className="text-4xl font-bold text-blue-400">{dashboard.nps_promoters + dashboard.nps_passives + dashboard.nps_detractors}</div>
                <div className="text-sm text-gray-400 mt-1">Total</div>
              </div>
            </div>
          </div>

          {/* Followed Advice */}
          <div className="bg-[#1a1a2e] rounded-lg p-6 border border-gray-800">
            <h2 className="text-xl font-bold mb-4">Did Users Follow Advice?</h2>
            <div className="grid grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-4xl font-bold text-green-400">{dashboard.followed_yes}</div>
                <div className="text-sm text-gray-400 mt-1">Yes</div>
              </div>
              <div className="text-center">
                <div className="text-4xl font-bold text-yellow-400">{dashboard.followed_partially}</div>
                <div className="text-sm text-gray-400 mt-1">Partially</div>
              </div>
              <div className="text-center">
                <div className="text-4xl font-bold text-red-400">{dashboard.followed_no}</div>
                <div className="text-sm text-gray-400 mt-1">No</div>
              </div>
              <div className="text-center border-l border-gray-700 pl-4">
                <div className="text-4xl font-bold text-blue-400">{dashboard.followed_yes + dashboard.followed_partially + dashboard.followed_no}</div>
                <div className="text-sm text-gray-400 mt-1">Total</div>
              </div>
            </div>
          </div>
        </div>
      ) : activeTab === 'rankings' && dashboard ? (
        <div className="max-w-7xl mx-auto">
          <div className="bg-[#1a1a2e] rounded-lg p-4 border border-gray-800">
            <h2 className="text-lg font-bold mb-3">Feature Rankings</h2>
            <div className="space-y-2">
              {dashboard.feature_rankings.map((feature, index) => (
                <div key={feature.feature_type} className="flex items-center gap-3 bg-[#0f0f23] rounded px-3 py-2">
                  {/* Rank */}
                  <span className="text-lg font-bold text-gray-500 w-8">#{index + 1}</span>
                  {/* Feature name */}
                  <span className="text-sm font-medium w-44 truncate">{feature.feature_type}</span>
                  {/* Rating distribution mini bar */}
                  <div className="flex gap-0.5 h-4 flex-1 max-w-xs">
                    {[1, 2, 3, 4, 5].map((star) => {
                      const count = feature.rating_distribution[String(star)] || 0;
                      const total = feature.total_ratings || 1;
                      const percentage = (count / total) * 100;
                      return (
                        <div
                          key={star}
                          className="flex-1 relative group cursor-help"
                          title={`${star}★: ${count} (${percentage.toFixed(0)}%)`}
                        >
                          <div className="h-full bg-gray-700 rounded-sm overflow-hidden">
                            <div
                              className={`w-full ${
                                star >= 4 ? 'bg-green-500' : star === 3 ? 'bg-yellow-500' : 'bg-red-500'
                              }`}
                              style={{ height: `${percentage}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {/* Rating count */}
                  <span className="text-xs text-gray-500 w-16 text-right">{feature.total_ratings} votes</span>
                  {/* Score */}
                  <span className={`text-lg font-bold w-12 text-right ${getRatingColor(feature.avg_rating)}`}>
                    {feature.avg_rating.toFixed(1)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : activeTab === 'comments' && comments ? (
        <div className="max-w-7xl mx-auto">
          {/* Comments count */}
          <div className="mb-4">
            <span className="text-gray-400">
              {comments.total} comments total • Page {comments.page} of {comments.total_pages}
            </span>
          </div>

          {/* Comments List */}
          <div className="space-y-4">
            {comments.comments.length === 0 ? (
              <div className="bg-[#1a1a2e] rounded-lg p-6 border border-gray-800 text-center text-gray-400">
                No comments found
              </div>
            ) : (
              comments.comments.map((comment) => (
                <div key={comment.id} className="bg-[#1a1a2e] rounded-lg p-4 border border-gray-800">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-gray-400 text-sm">Team #{comment.team_id} • GW{comment.gameweek}</span>
                    <span className="text-yellow-400">{renderStars(comment.rating)}</span>
                  </div>
                  <p className="text-gray-300">&quot;{comment.comment}&quot;</p>
                  <p className="text-xs text-gray-500 mt-2">
                    {new Date(comment.created_at).toLocaleString()}
                  </p>
                </div>
              ))
            )}
          </div>

          {/* Pagination */}
          {comments.total_pages > 1 && (
            <div className="flex justify-center gap-2 mt-6">
              <button
                onClick={() => setCommentsPage((p) => Math.max(1, p - 1))}
                disabled={commentsPage === 1}
                className="px-4 py-2 bg-[#1a1a2e] rounded disabled:opacity-50 hover:bg-gray-800"
              >
                Previous
              </button>
              <button
                onClick={() => setCommentsPage((p) => Math.min(comments.total_pages, p + 1))}
                disabled={commentsPage === comments.total_pages}
                className="px-4 py-2 bg-[#1a1a2e] rounded disabled:opacity-50 hover:bg-gray-800"
              >
                Next
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="text-center text-gray-400 py-12">No data available</div>
      )}
    </div>
  );
}
