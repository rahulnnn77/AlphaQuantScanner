import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  BarChart2, 
  Sliders, 
  Users, 
  UserCheck, 
  LogOut, 
  KeyRound, 
  Activity, 
  ShieldCheck, 
  Clock, 
  AlertCircle 
} from 'lucide-react';

export default function Layout({ children }) {
  const { user, logout, brokerSession, isAdmin } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-[#0B0F19] text-gray-100 overflow-hidden font-sans">
      {/* Sidebar Navigation */}
      <aside className="w-64 bg-[#111827] border-r border-[#1F2937] flex flex-col justify-between">
        <div>
          {/* Logo / Branding */}
          <div className="p-5 border-b border-[#1F2937] flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-9 h-9 rounded-lg bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
                <BarChart2 className="w-5 h-5" />
              </div>
              <div>
                <h1 className="font-bold text-base tracking-wide text-white">AlphaQuant</h1>
                <p className="text-[11px] text-gray-400 font-mono tracking-tight">Dhan Market Screener</p>
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-4 space-y-1.5">
            <NavLink
              to="/dashboard"
              end
              className={({ isActive }) =>
                `flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-[#161F30]'
                }`
              }
            >
              <BarChart2 className="w-4 h-4" />
              <span>Live Screener</span>
            </NavLink>

            {isAdmin && (
              <>
                <NavLink
                  to="/admin/screener-config"
                  className={({ isActive }) =>
                    `flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-[#161F30]'
                    }`
                  }
                >
                  <Sliders className="w-4 h-4" />
                  <span>Screener Rules</span>
                </NavLink>

                <NavLink
                  to="/admin/users"
                  className={({ isActive }) =>
                    `flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-[#161F30]'
                    }`
                  }
                >
                  <Users className="w-4 h-4" />
                  <span>User Management</span>
                </NavLink>

                <NavLink
                  to="/admin/broker-auth"
                  className={({ isActive }) =>
                    `flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-[#161F30]'
                    }`
                  }
                >
                  <KeyRound className="w-4 h-4" />
                  <span>Dhan Broker Auth</span>
                </NavLink>
              </>
            )}

            <NavLink
              to="/profile"
              className={({ isActive }) =>
                `flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-[#161F30]'
                }`
              }
            >
              <UserCheck className="w-4 h-4" />
              <span>Broker Profile</span>
            </NavLink>
          </nav>
        </div>

        {/* User Card & Logout in Sidebar Footer */}
        <div className="p-4 border-t border-[#1F2937]">
          <div className="flex items-center justify-between mb-3 px-1">
            <div className="flex items-center space-x-2">
              <div className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center text-xs font-bold text-gray-300">
                {user?.username?.[0]?.toUpperCase() || 'U'}
              </div>
              <div className="truncate">
                <p className="text-xs font-semibold text-white truncate">{user?.username}</p>
                <span className={`inline-block text-[10px] uppercase font-mono px-1.5 py-0.2 rounded ${
                  isAdmin ? 'bg-indigo-900/60 text-indigo-300' : 'bg-gray-800 text-gray-400'
                }`}>
                  {user?.role}
                </span>
              </div>
            </div>
            <button
              onClick={handleLogout}
              title="Sign Out"
              className="text-gray-400 hover:text-rose-400 p-1.5 rounded-md hover:bg-[#1F2937] transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Status Bar */}
        <header className="h-14 bg-[#111827] border-b border-[#1F2937] px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-6">
            {/* Market Status NSE / BSE */}
            <div className="flex items-center space-x-2 text-xs">
              <Clock className="w-3.5 h-3.5 text-gray-400" />
              <span className="text-gray-400 font-medium">NSE/BSE:</span>
              <div className="flex items-center space-x-1.5">
                <span className={`w-2 h-2 rounded-full ${brokerSession.market_open ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
                <span className={`font-semibold ${brokerSession.market_open ? 'text-emerald-400' : 'text-gray-400'}`}>
                  {brokerSession.market_open ? 'MARKET OPEN' : 'MARKET CLOSED'}
                </span>
              </div>
            </div>

            {/* Broker Health */}
            <div className="flex items-center space-x-2 text-xs border-l border-[#1F2937] pl-6">
              <Activity className="w-3.5 h-3.5 text-gray-400" />
              <span className="text-gray-400 font-medium">Dhan HQ Feed:</span>
              <div className="flex items-center space-x-1.5">
                <span className={`w-2 h-2 rounded-full ${brokerSession.authenticated ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                <span className={`font-semibold ${brokerSession.authenticated ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {brokerSession.authenticated 
                    ? `CONNECTED (${brokerSession.client_id || 'Active'})`
                    : 'OFFLINE / UNLINKED'}
                </span>
              </div>
            </div>
          </div>

          {/* Right Status Actions */}
          <div className="flex items-center space-x-3 text-xs">
            {isAdmin && !brokerSession.authenticated && (
              <button 
                onClick={() => navigate('/admin/broker-auth')}
                className="flex items-center space-x-1.5 px-3 py-1.5 bg-amber-500/10 border border-amber-500/30 text-amber-400 rounded-md hover:bg-amber-500/20 transition-colors"
              >
                <AlertCircle className="w-3.5 h-3.5" />
                <span>Link Dhan Broker</span>
              </button>
            )}
            <div className="px-2.5 py-1 rounded-md bg-[#161F30] border border-[#1F2937] text-gray-400 font-mono text-[11px]">
              IST (UTC+5:30)
            </div>
          </div>
        </header>

        {/* Scrollable Viewport */}
        <main className="flex-1 overflow-y-auto p-6 bg-[#0B0F19]">
          {children}
        </main>
      </div>
    </div>
  );
}
