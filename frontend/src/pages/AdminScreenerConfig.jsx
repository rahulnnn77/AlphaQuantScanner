import React, { useState, useEffect } from 'react';
import api from '../api';
import { Sliders, Plus, Trash2, CheckCircle2, ToggleLeft, ToggleRight, AlertCircle, X } from 'lucide-react';

export default function AdminScreenerConfig() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    universe: 'NIFTY50',
    min_price: 50,
    max_price: 50000,
    min_change_pct: 1.0,
    min_volume_ratio: 1.2,
    rsi_min: 50,
    rsi_max: 75,
    moving_average: 'ABOVE_SMA20',
  });
  const [error, setError] = useState('');

  const fetchRules = async () => {
    try {
      const res = await api.get('/screener/rules');
      setRules(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, []);

  const handleToggleActive = async (rule) => {
    try {
      await api.put(`/screener/rules/${rule.id}`, {
        is_active: !rule.is_active,
      });
      fetchRules();
    } catch (err) {
      alert('Failed to update rule state');
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this rule?')) return;
    try {
      await api.delete(`/screener/rules/${id}`);
      fetchRules();
    } catch (err) {
      alert('Failed to delete rule');
    }
  };

  const handleCreateRule = async (e) => {
    e.preventDefault();
    setError('');
    try {
      await api.post('/screener/rules', {
        name: formData.name,
        description: formData.description,
        universe: formData.universe,
        is_active: true,
        criteria: {
          min_price: Number(formData.min_price),
          max_price: Number(formData.max_price),
          min_change_pct: formData.min_change_pct ? Number(formData.min_change_pct) : null,
          min_volume_ratio: formData.min_volume_ratio ? Number(formData.min_volume_ratio) : null,
          rsi_min: formData.rsi_min ? Number(formData.rsi_min) : null,
          rsi_max: formData.rsi_max ? Number(formData.rsi_max) : null,
          moving_average: formData.moving_average || null,
        },
      });
      setShowModal(false);
      fetchRules();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create rule');
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center space-x-2">
            <Sliders className="w-5 h-5 text-indigo-400" />
            <span>Screener Strategy & Rules Engine</span>
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Define quantitative screening parameters that evaluate live market quotes for all connected users.
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="flex items-center space-x-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-lg shadow-indigo-600/20 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>New Screening Rule</span>
        </button>
      </div>

      {/* Rules List Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {rules.map((rule) => (
          <div key={rule.id} className="bg-[#111827] border border-[#1F2937] rounded-xl p-5 shadow-lg relative">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center space-x-2">
                  <h3 className="text-sm font-bold text-white">{rule.name}</h3>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#161F30] border border-[#1F2937] text-gray-400">
                    {rule.universe}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-1">{rule.description || 'Custom technical scanner rule'}</p>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleToggleActive(rule)}
                  className="text-gray-400 hover:text-white transition-colors"
                  title={rule.is_active ? 'Deactivate rule' : 'Activate rule'}
                >
                  {rule.is_active ? (
                    <ToggleRight className="w-6 h-6 text-emerald-400" />
                  ) : (
                    <ToggleLeft className="w-6 h-6 text-gray-600" />
                  )}
                </button>
                <button
                  onClick={() => handleDelete(rule.id)}
                  className="text-gray-500 hover:text-rose-400 p-1 transition-colors"
                  title="Delete Rule"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Criteria Badges */}
            <div className="mt-4 pt-3 border-t border-[#1F2937] flex flex-wrap gap-2 text-[11px]">
              {rule.criteria.min_price && (
                <span className="px-2 py-1 bg-[#161F30] border border-[#1F2937] rounded text-gray-300">
                  Min ₹{rule.criteria.min_price}
                </span>
              )}
              {rule.criteria.min_change_pct && (
                <span className="px-2 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded text-emerald-400">
                  Change &gt;= {rule.criteria.min_change_pct}%
                </span>
              )}
              {rule.criteria.min_volume_ratio && (
                <span className="px-2 py-1 bg-amber-500/10 border border-amber-500/20 rounded text-amber-300">
                  Vol &gt;= {rule.criteria.min_volume_ratio}x
                </span>
              )}
              {rule.criteria.rsi_min && (
                <span className="px-2 py-1 bg-indigo-500/10 border border-indigo-500/20 rounded text-indigo-300">
                  RSI {rule.criteria.rsi_min} - {rule.criteria.rsi_max || 100}
                </span>
              )}
              {rule.criteria.moving_average && (
                <span className="px-2 py-1 bg-purple-500/10 border border-purple-500/20 rounded text-purple-300 font-mono">
                  {rule.criteria.moving_average}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Create Rule Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-[#111827] border border-[#1F2937] rounded-xl max-w-lg w-full p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-[#1F2937] mb-4">
              <h2 className="text-sm font-bold text-white">Create Stock Screener Rule</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            {error && (
              <div className="mb-4 p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                {error}
              </div>
            )}

            <form onSubmit={handleCreateRule} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-medium text-gray-300 mb-1">Rule Name</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. Volume Surge & RSI Breakout"
                  className="w-full px-3 py-2 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-gray-100"
                />
              </div>

              <div>
                <label className="block font-medium text-gray-300 mb-1">Description</label>
                <input
                  type="text"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="e.g. Finds momentum stocks above EMA with heavy volume"
                  className="w-full px-3 py-2 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-gray-100"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-gray-300 mb-1">Target Universe</label>
                  <select
                    value={formData.universe}
                    onChange={(e) => setFormData({ ...formData, universe: e.target.value })}
                    className="w-full px-3 py-2 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-gray-100"
                  >
                    <option value="NIFTY50">NIFTY 50</option>
                    <option value="BANKNIFTY">BANK NIFTY</option>
                    <option value="ALL">ALL WATCHLISTS</option>
                  </select>
                </div>
                <div>
                  <label className="block font-medium text-gray-300 mb-1">Moving Average Condition</label>
                  <select
                    value={formData.moving_average}
                    onChange={(e) => setFormData({ ...formData, moving_average: e.target.value })}
                    className="w-full px-3 py-2 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-gray-100"
                  >
                    <option value="ABOVE_SMA20">Price &gt; 20 SMA</option>
                    <option value="ABOVE_EMA50">Price &gt; 50 EMA</option>
                    <option value="GOLDEN_CROSS">20 SMA &gt; 50 EMA</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-gray-300 mb-1">Min Price (₹)</label>
                  <input
                    type="number"
                    value={formData.min_price}
                    onChange={(e) => setFormData({ ...formData, min_price: e.target.value })}
                    className="w-full px-3 py-2 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-gray-100"
                  />
                </div>
                <div>
                  <label className="block font-medium text-gray-300 mb-1">Min % Change Today</label>
                  <input
                    type="number"
                    step="0.1"
                    value={formData.min_change_pct}
                    onChange={(e) => setFormData({ ...formData, min_change_pct: e.target.value })}
                    className="w-full px-3 py-2 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-gray-100"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-gray-300 mb-1">Min Volume Surge (x Ratio)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={formData.min_volume_ratio}
                    onChange={(e) => setFormData({ ...formData, min_volume_ratio: e.target.value })}
                    className="w-full px-3 py-2 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-gray-100"
                  />
                </div>
                <div>
                  <label className="block font-medium text-gray-300 mb-1">RSI Range (Min)</label>
                  <input
                    type="number"
                    value={formData.rsi_min}
                    onChange={(e) => setFormData({ ...formData, rsi_min: e.target.value })}
                    className="w-full px-3 py-2 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-gray-100"
                  />
                </div>
              </div>

              <div className="pt-3 flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-3 py-2 bg-[#161F30] text-gray-300 rounded-lg hover:bg-[#1E293B]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-semibold"
                >
                  Save Rule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
