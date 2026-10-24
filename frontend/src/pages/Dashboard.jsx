import React, { useState, useEffect } from 'react';
import api from '../api';
import { 
  Search, 
  RefreshCw, 
  ArrowUpRight, 
  ArrowDownRight, 
  Filter, 
  Activity, 
  SlidersHorizontal,
  Clock,
  TrendingUp,
  Flame,
  CheckCircle2
} from 'lucide-react';

export default function Dashboard() {
  const [stocks, setStocks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedUniverse, setSelectedUniverse] = useState('NIFTY50');
  const [filterTag, setFilterTag] = useState('ALL');
  const [lastScanned, setLastScanned] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchResults = async (isManual = false) => {
    if (isManual) setRefreshing(true);
    try {
      const res = await api.get(`/screener/results?universe=${selectedUniverse}`);
      setStocks(res.data);
      if (res.data.length > 0) {
        setLastScanned(res.data[0].last_updated || new Date().toLocaleTimeString());
      }
    } catch (err) {
      console.error('Failed to fetch screener results', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const triggerManualScan = async () => {
    setRefreshing(true);
    try {
      const res = await api.post(`/screener/scan?universe=${selectedUniverse}`);
      setStocks(res.data);
      if (res.data.length > 0) {
        setLastScanned(res.data[0].last_updated || new Date().toLocaleTimeString());
      }
    } catch (err) {
      console.error('Scan failed', err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchResults();
  }, [selectedUniverse]);

  useEffect(() => {
    let interval;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchResults();
      }, 15000); // 15-second cycle
    }
    return () => clearInterval(interval);
  }, [autoRefresh, selectedUniverse]);

  // Filtering
  const filteredStocks = stocks.filter((stock) => {
    const matchesSearch = 
      stock.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
      stock.name.toLowerCase().includes(searchTerm.toLowerCase());
    
    if (!matchesSearch) return false;
    if (filterTag === 'GAINERS') return stock.change_pct > 0;
    if (filterTag === 'LOSERS') return stock.change_pct < 0;
    if (filterTag === 'VOL_SURGE') return stock.volume_surge_x >= 1.5;
    if (filterTag === 'MOMENTUM') return stock.rsi >= 60;
    return true;
  });

  // Top metrics
  const totalStocks = stocks.length;
  const gainers = stocks.filter(s => s.change_pct > 0).length;
  const losers = stocks.filter(s => s.change_pct < 0).length;
  const volumeSurges = stocks.filter(s => s.volume_surge_x >= 1.5).length;

  return (
    <div className="space-y-6">
      {/* Top Header & Metrics Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center space-x-2">
            <span>Market Screener Dashboard</span>
            <span className="text-xs bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 font-mono px-2 py-0.5 rounded">
              Live Feed
            </span>
          </h1>
          <p className="text-xs text-gray-400 mt-0.5 flex items-center space-x-2">
            <Clock className="w-3 h-3" />
            <span>Last Scanned: {lastScanned || 'Just now'}</span>
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-3">
          <label className="flex items-center space-x-2 text-xs text-gray-300 bg-[#111827] border border-[#1F2937] px-3 py-2 rounded-lg cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded bg-[#0B0F19] border-gray-700 text-indigo-600 focus:ring-0"
            />
            <span>Auto Refresh (15s)</span>
          </label>

          <button
            onClick={triggerManualScan}
            disabled={refreshing}
            className="flex items-center space-x-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow-lg shadow-indigo-600/20 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span>{refreshing ? 'Scanning Universe...' : 'Run Scan'}</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#111827] border border-[#1F2937] rounded-xl p-4">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium">Scanned Universe</span>
            <Activity className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white font-mono">{totalStocks}</div>
          <span className="text-[11px] text-gray-400">{selectedUniverse} stocks monitored</span>
        </div>

        <div className="bg-[#111827] border border-[#1F2937] rounded-xl p-4">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium">Advance / Gainers</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 font-mono">{gainers}</div>
          <span className="text-[11px] text-gray-400">Green session bias</span>
        </div>

        <div className="bg-[#111827] border border-[#1F2937] rounded-xl p-4">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium">Decline / Losers</span>
            <ArrowDownRight className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-bold text-rose-400 font-mono">{losers}</div>
          <span className="text-[11px] text-gray-400">Under pressure</span>
        </div>

        <div className="bg-[#111827] border border-[#1F2937] rounded-xl p-4">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium">Volume Breakouts</span>
            <Flame className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400 font-mono">{volumeSurges}</div>
          <span className="text-[11px] text-gray-400">Surge &gt;= 1.5x volume</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-[#111827] border border-[#1F2937] rounded-xl p-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center space-x-3 w-full md:w-auto">
          {/* Universe Selector */}
          <select
            value={selectedUniverse}
            onChange={(e) => setSelectedUniverse(e.target.value)}
            className="bg-[#0B0F19] border border-[#1F2937] text-gray-200 text-xs rounded-lg px-3 py-2 font-medium focus:outline-none focus:border-indigo-500"
          >
            <option value="NIFTY50">NSE: NIFTY 50</option>
            <option value="BANKNIFTY">NSE: BANK NIFTY</option>
          </select>

          {/* Quick Tag Filters */}
          <div className="flex items-center space-x-1 bg-[#0B0F19] p-1 border border-[#1F2937] rounded-lg">
            {['ALL', 'GAINERS', 'LOSERS', 'VOL_SURGE', 'MOMENTUM'].map((tag) => (
              <button
                key={tag}
                onClick={() => setFilterTag(tag)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-all ${
                  filterTag === tag
                    ? 'bg-indigo-600 text-white'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {tag.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Search Input */}
        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-500" />
          <input
            type="text"
            placeholder="Search by Symbol or Name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-[#0B0F19] border border-[#1F2937] rounded-lg pl-9 pr-4 py-2 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500"
          />
        </div>
      </div>

      {/* Main Stock Table */}
      <div className="bg-[#111827] border border-[#1F2937] rounded-xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#161F30] text-gray-400 uppercase font-mono tracking-wider border-b border-[#1F2937]">
              <tr>
                <th className="py-3 px-4">Symbol / Name</th>
                <th className="py-3 px-4 text-right">LTP (INR)</th>
                <th className="py-3 px-4 text-right">Change %</th>
                <th className="py-3 px-4 text-right">Day High / Low</th>
                <th className="py-3 px-4 text-right">Volume</th>
                <th className="py-3 px-4 text-center">Vol Surge</th>
                <th className="py-3 px-4 text-center">RSI (14)</th>
                <th className="py-3 px-4">Triggered Criteria / Strategy</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1F2937]">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-gray-500">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-500" />
                    <span>Loading market quotes and indicators...</span>
                  </td>
                </tr>
              ) : filteredStocks.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-gray-500">
                    <span>No stocks matching the selected criteria.</span>
                  </td>
                </tr>
              ) : (
                filteredStocks.map((stock) => {
                  const isBullish = stock.change_pct >= 0;
                  return (
                    <tr key={stock.symbol} className="hover:bg-[#161F30]/60 transition-colors">
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-white text-sm">{stock.symbol}</div>
                        <div className="text-[11px] text-gray-400 truncate max-w-[180px]">{stock.name}</div>
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono font-semibold text-white">
                        ₹{stock.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className={`inline-flex items-center space-x-1 font-mono font-bold px-2 py-0.5 rounded text-xs ${
                          isBullish 
                            ? 'text-emerald-400 bg-emerald-500/10' 
                            : 'text-rose-400 bg-rose-500/10'
                        }`}>
                          {isBullish ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                          <span>{isBullish ? `+${stock.change_pct}%` : `${stock.change_pct}%`}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono text-gray-300">
                        <div>H: ₹{stock.high.toFixed(1)}</div>
                        <div className="text-[10px] text-gray-500">L: ₹{stock.low.toFixed(1)}</div>
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono text-gray-300">
                        {stock.volume.toLocaleString('en-IN')}
                      </td>
                      <td className="py-3.5 px-4 text-center font-mono">
                        <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                          stock.volume_surge_x >= 1.5
                            ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                            : 'text-gray-400'
                        }`}>
                          {stock.volume_surge_x}x
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-center font-mono">
                        <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                          stock.rsi >= 70 ? 'text-rose-400 bg-rose-500/10' :
                          stock.rsi >= 60 ? 'text-emerald-400 bg-emerald-500/10' :
                          stock.rsi <= 35 ? 'text-blue-400 bg-blue-500/10' : 'text-gray-300'
                        }`}>
                          {stock.rsi}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="flex flex-wrap gap-1">
                          {stock.triggered_criteria?.map((crit, idx) => (
                            <span 
                              key={idx}
                              className="px-2 py-0.5 rounded text-[10px] font-medium bg-indigo-500/10 text-indigo-300 border border-indigo-500/20"
                            >
                              {crit}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
