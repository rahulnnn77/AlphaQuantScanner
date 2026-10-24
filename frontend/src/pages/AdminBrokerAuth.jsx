import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../context/AuthContext';
import { KeyRound, Shield, CheckCircle2, AlertCircle, RefreshCw, Lock, ExternalLink } from 'lucide-react';

export default function AdminBrokerAuth() {
  const { brokerSession, refreshBrokerStatus } = useAuth();
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [requestToken, setRequestToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    if (brokerSession.client_id) {
      setApiKey(brokerSession.client_id);
    }
  }, [brokerSession.client_id]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      const res = await api.post('/auth/dhan-login', {
        api_key: apiKey.trim(),
        api_secret: apiSecret.trim() || null,
        request_token: requestToken.trim() || null,
      });

      if (res.data.status === 'authenticated') {
        setSuccess('Dhan Broker connected successfully! Tokens encrypted and persisted securely on server.');
        await refreshBrokerStatus();
        setTimeout(() => {
          navigate('/dashboard');
        }, 1200);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Broker authentication failed. Verify your Client ID / Token.');
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm('Are you sure you want to disconnect the active Dhan broker session?')) return;
    try {
      await api.post('/auth/dhan-logout');
      await refreshBrokerStatus();
      setSuccess('Broker session disconnected.');
    } catch (err) {
      setError('Failed to clear session.');
    }
  };

  return (
    <div className="max-w-2xl mx-auto py-4">
      {/* Page Title */}
      <div className="mb-6">
        <h1 className="text-xl font-bold text-white flex items-center space-x-2">
          <KeyRound className="w-5 h-5 text-indigo-400" />
          <span>Dhan HQ Broker Authentication</span>
        </h1>
        <p className="text-xs text-gray-400 mt-1">
          Connect your Dhan Trading Account credentials. Tokens are encrypted and persisted securely on the backend only.
        </p>
      </div>

      {/* Active Connection Status Banner */}
      <div className={`p-4 rounded-xl border mb-6 flex items-center justify-between ${
        brokerSession.authenticated
          ? 'bg-emerald-500/10 border-emerald-500/30'
          : 'bg-amber-500/10 border-amber-500/30'
      }`}>
        <div className="flex items-center space-x-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${
            brokerSession.authenticated ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'
          }`}>
            {brokerSession.authenticated ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          </div>
          <div>
            <h3 className={`text-sm font-semibold ${brokerSession.authenticated ? 'text-emerald-300' : 'text-amber-300'}`}>
              {brokerSession.authenticated ? 'Broker Connection Active' : 'No Active Broker Session'}
            </h3>
            <p className="text-xs text-gray-400">
              {brokerSession.authenticated 
                ? `Persisted Client ID: ${brokerSession.client_id} (Server Auto-reloads & survives reboots)`
                : 'Input your Dhan API details below to enable live market scanning.'}
            </p>
          </div>
        </div>

        {brokerSession.authenticated && (
          <button
            onClick={handleDisconnect}
            className="px-3 py-1.5 bg-rose-500/20 border border-rose-500/30 text-rose-300 hover:bg-rose-500/30 rounded-lg text-xs font-medium transition-colors"
          >
            Disconnect
          </button>
        )}
      </div>

      {/* Auth Form Card */}
      <div className="bg-[#111827] border border-[#1F2937] rounded-xl p-6 shadow-xl">
        {error && (
          <div className="mb-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-center space-x-2 text-rose-400 text-xs">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="mb-4 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center space-x-2 text-emerald-400 text-xs">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{success}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1.5">
              1. Dhan Client ID / API Key <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="e.g. 1000000001"
              className="w-full px-3.5 py-2.5 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-500"
            />
            <span className="text-[11px] text-gray-500 mt-1 block">Your 10-digit Dhan registered Client ID</span>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1.5">
              2. API Secret (App Secret)
            </label>
            <input
              type="password"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              placeholder="Optional if using direct access token"
              className="w-full px-3.5 py-2.5 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-indigo-500"
            />
            <span className="text-[11px] text-gray-500 mt-1 block">Generated from Dhan Web / Developer Console</span>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1.5">
              3. Request Token / Access Token <span className="text-rose-400">*</span>
            </label>
            <textarea
              required
              rows={3}
              value={requestToken}
              onChange={(e) => setRequestToken(e.target.value)}
              placeholder="Paste Consent Token ID or Full JWT Access Token"
              className="w-full px-3.5 py-2 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-sm text-gray-100 font-mono placeholder-gray-600 focus:outline-none focus:border-indigo-500"
            />
            <span className="text-[11px] text-gray-500 mt-1 block">
              Direct access token generated from Dhan HQ portal or OAuth callback token
            </span>
          </div>

          <div className="pt-2">
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-sm rounded-lg transition-colors flex items-center justify-center space-x-2 shadow-lg shadow-indigo-600/25"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Validating & Encrypting Session...</span>
                </>
              ) : (
                <>
                  <Lock className="w-4 h-4" />
                  <span>Connect Broker & Login</span>
                </>
              )}
            </button>
          </div>
        </form>

        <div className="mt-6 pt-4 border-t border-[#1F2937] flex items-center justify-between text-xs text-gray-500">
          <span className="flex items-center space-x-1">
            <Shield className="w-3.5 h-3.5 text-indigo-400" />
            <span>End-to-end encrypted token storage</span>
          </span>
          <a
            href="https://dhanhq.co/docs/"
            target="_blank"
            rel="noreferrer"
            className="text-indigo-400 hover:underline flex items-center space-x-1"
          >
            <span>Dhan API Docs</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    </div>
  );
}
