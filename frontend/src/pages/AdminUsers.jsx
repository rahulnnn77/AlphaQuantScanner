import React, { useState, useEffect } from 'react';
import api from '../api';
import { Users, UserPlus, Trash2, CheckCircle2, XCircle, ShieldCheck, User } from 'lucide-react';

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('viewer');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const fetchUsers = async () => {
    try {
      const res = await api.get('/users');
      setUsers(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    try {
      await api.post('/users', { username, password, role });
      setSuccess(`User "${username}" created successfully.`);
      setUsername('');
      setPassword('');
      fetchUsers();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create user');
    }
  };

  const handleToggleStatus = async (u) => {
    try {
      await api.patch(`/users/${u.id}`, { is_active: !u.is_active });
      fetchUsers();
    } catch (err) {
      alert('Failed to update user status');
    }
  };

  const handleDelete = async (u) => {
    if (!confirm(`Are you sure you want to delete user "${u.username}"?`)) return;
    try {
      await api.delete(`/users/${u.id}`);
      fetchUsers();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete user');
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center space-x-2">
          <Users className="w-5 h-5 text-indigo-400" />
          <span>User Access & Role Management</span>
        </h1>
        <p className="text-xs text-gray-400 mt-1">
          Create viewer credentials so team members can view live scanner results without having broker API secrets.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Create User Form */}
        <div className="bg-[#111827] border border-[#1F2937] rounded-xl p-5 shadow-xl h-fit">
          <h2 className="text-sm font-semibold text-white mb-3 flex items-center space-x-2">
            <UserPlus className="w-4 h-4 text-indigo-400" />
            <span>Grant New User Access</span>
          </h2>

          {error && (
            <div className="mb-3 p-2 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
              {error}
            </div>
          )}
          {success && (
            <div className="mb-3 p-2 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs">
              {success}
            </div>
          )}

          <form onSubmit={handleCreateUser} className="space-y-3 text-xs">
            <div>
              <label className="block text-gray-300 mb-1">Username</label>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. analyst_john"
                className="w-full px-3 py-2 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-gray-100"
              />
            </div>

            <div>
              <label className="block text-gray-300 mb-1">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Temporary password"
                className="w-full px-3 py-2 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-gray-100"
              />
            </div>

            <div>
              <label className="block text-gray-300 mb-1">Role</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full px-3 py-2 bg-[#0B0F19] border border-[#1F2937] rounded-lg text-gray-100"
              >
                <option value="viewer">Viewer (Read-Only Screener)</option>
                <option value="admin">Administrator (Full Control)</option>
              </select>
            </div>

            <button
              type="submit"
              className="w-full py-2 px-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium text-xs shadow-md transition-colors"
            >
              Add User
            </button>
          </form>
        </div>

        {/* Users Table */}
        <div className="md:col-span-2 bg-[#111827] border border-[#1F2937] rounded-xl overflow-hidden shadow-xl">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#161F30] text-gray-400 font-mono border-b border-[#1F2937]">
              <tr>
                <th className="py-3 px-4">User</th>
                <th className="py-3 px-4">Role</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1F2937]">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-[#161F30]/40 transition-colors">
                  <td className="py-3 px-4 flex items-center space-x-2">
                    <div className="w-6 h-6 rounded-full bg-gray-800 flex items-center justify-center font-bold text-[10px]">
                      {u.username[0].toUpperCase()}
                    </div>
                    <span className="font-semibold text-white">{u.username}</span>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                      u.role === 'admin'
                        ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
                        : 'bg-gray-800 text-gray-300'
                    }`}>
                      {u.role.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <button
                      onClick={() => handleToggleStatus(u)}
                      className={`inline-flex items-center space-x-1 text-[11px] font-medium ${
                        u.is_active ? 'text-emerald-400' : 'text-gray-500'
                      }`}
                    >
                      {u.is_active ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                      <span>{u.is_active ? 'Active' : 'Disabled'}</span>
                    </button>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={() => handleDelete(u)}
                      className="text-gray-500 hover:text-rose-400 transition-colors p-1"
                      title="Revoke access"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
