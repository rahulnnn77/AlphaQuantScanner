import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Shield, Lock, User, ArrowRight, AlertCircle, BarChart2 } from 'lucide-react';

export default function Login() {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('Admin@12345');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid username or password');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickFill = (role) => {
    if (role === 'admin') {
      setUsername('admin');
      setPassword('Admin@12345');
    } else {
      setUsername('viewer');
      setPassword('Viewer@12345');
    }
  };

  return (
    <div className="min-h-screen bg-[#0B0F19] flex flex-col justify-center items-center px-4">
      {/* Brand Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-indigo-600/20 border border-indigo-500/30 text-indigo-400 mb-3 shadow-lg shadow-indigo-500/10">
          <BarChart2 className="w-6 h-6" />
        </div>
        <h1 className="text-2xl font-bold text-white tracking-tight">AlphaQuant Scanner</h1>
        <p className="text-sm text-gray-400 mt-1">Institutional-grade Indian Stock Market Intelligence</p>
      </div>

      {/* Login Card */}
      <div className="w-full max-w-md bg-[#111827] border border-[#1F2937] rounded-xl p-8 shadow-2xl">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-white">Sign In to Workspace</h2>
          <p className="text-xs text-gray-400 mt-0.5">Enter your credentials granted by the system administrator</p>
        </div>

        {error && (
          <div className="mb-5 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-center space-x-2 text-rose-400 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1.5">Username</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                <User className="w-4 h-4" />
              </div>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                className="w-full pl-10 pr-4 py-2.5 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1.5">Password</label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-500">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-10 pr-4 py-2.5 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-colors"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 flex items-center justify-center space-x-2 py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-sm rounded-lg transition-colors shadow-lg shadow-indigo-600/25"
          >
            <span>{loading ? 'Authenticating...' : 'Sign In'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        {/* Demo Fast Login Helpers */}
        <div className="mt-6 pt-5 border-t border-[#1F2937]">
          <p className="text-[11px] text-gray-400 font-medium mb-2.5 text-center">Quick Demo Credentials:</p>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => handleQuickFill('admin')}
              className="py-1.5 px-2 bg-[#161F30] hover:bg-[#1E293B] border border-[#1F2937] rounded-md text-xs text-indigo-300 font-mono transition-colors text-center"
            >
              Admin Mode
            </button>
            <button
              type="button"
              onClick={() => handleQuickFill('viewer')}
              className="py-1.5 px-2 bg-[#161F30] hover:bg-[#1E293B] border border-[#1F2937] rounded-md text-xs text-gray-300 font-mono transition-colors text-center"
            >
              Viewer Mode
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
