import React, { useState, useEffect } from 'react';
import api from '../api';
import { UserCheck, Shield, Check, AlertCircle, RefreshCw } from 'lucide-react';

export default function Profile() {
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchProfile = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/profile/');
      setProfileData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Broker profile could not be loaded. Please ensure Dhan is connected.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-gray-500">
        <RefreshCw className="w-6 h-6 animate-spin mb-2 text-indigo-500" />
        <span className="text-xs">Fetching profile details from DhanHQ API...</span>
      </div>
    );
  }

  const dhan = profileData?.dhan_profile;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center space-x-2">
          <UserCheck className="w-5 h-5 text-indigo-400" />
          <span>Broker Account Profile</span>
        </h1>
        <p className="text-xs text-gray-400 mt-1">
          Detailed Dhan account metadata, authorized product subscriptions, and trading permissions.
        </p>
      </div>

      {error ? (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start space-x-3 text-amber-300 text-xs">
          <AlertCircle className="w-5 h-5 shrink-0 text-amber-400" />
          <div>
            <span className="font-semibold block">Dhan Broker Not Connected</span>
            <p className="text-gray-400 mt-1">{error}</p>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Main Account Details Card */}
          <div className="bg-[#111827] border border-[#1F2937] rounded-xl p-6 shadow-xl">
            <div className="flex items-center justify-between pb-4 border-b border-[#1F2937] mb-6">
              <div className="flex items-center space-x-3">
                <div className="w-12 h-12 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 text-lg font-bold">
                  {dhan?.user_name?.[0] || 'D'}
                </div>
                <div>
                  <h2 className="text-base font-bold text-white">{dhan?.user_name}</h2>
                  <p className="text-xs text-gray-400 font-mono">Dhan Client ID: {dhan?.client_id}</p>
                </div>
              </div>
              <div className="flex items-center space-x-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
                <Check className="w-3.5 h-3.5" />
                <span>Session Active</span>
              </div>
            </div>

            {/* Account Attributes Grid */}
            <div className="grid grid-cols-2 gap-4 text-xs mb-6">
              <div className="p-3 bg-[#0B0F19] rounded-lg border border-[#1F2937]">
                <span className="text-gray-500 block mb-1">Application User</span>
                <span className="font-semibold text-white">{profileData?.app_user} ({profileData?.app_role})</span>
              </div>
              <div className="p-3 bg-[#0B0F19] rounded-lg border border-[#1F2937]">
                <span className="text-gray-500 block mb-1">Token Status</span>
                <span className="font-semibold text-emerald-400">Verified & Encrypted</span>
              </div>
            </div>

            {/* Active Products Badges */}
            <div className="mb-6">
              <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2.5">
                Active Trading Products
              </h3>
              <div className="flex flex-wrap gap-2">
                {dhan?.active_products?.map((prod) => (
                  <span
                    key={prod}
                    className="px-3 py-1 rounded-md text-xs font-mono font-medium bg-indigo-500/10 text-indigo-300 border border-indigo-500/30"
                  >
                    {prod}
                  </span>
                ))}
              </div>
            </div>

            {/* Enabled Exchanges Badges */}
            <div>
              <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2.5">
                Enabled Indian Exchanges
              </h3>
              <div className="flex flex-wrap gap-2">
                {dhan?.enabled_exchanges?.map((exch) => (
                  <span
                    key={exch}
                    className="px-3 py-1 rounded-md text-xs font-mono font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/30"
                  >
                    {exch}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
