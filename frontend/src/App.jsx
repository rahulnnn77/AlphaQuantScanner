import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import AdminBrokerAuth from './pages/AdminBrokerAuth';
import AdminScreenerConfig from './pages/AdminScreenerConfig';
import AdminUsers from './pages/AdminUsers';
import Profile from './pages/Profile';

const ProtectedRoute = ({ children, requireAdmin = false }) => {
  const { user, isAdmin } = useAuth();
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (requireAdmin && !isAdmin) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Layout>{children}</Layout>;
};

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />

          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            }
          />

          {/* Admin Dedicated Routes */}
          <Route
            path="/admin/broker-auth"
            element={
              <ProtectedRoute requireAdmin={true}>
                <AdminBrokerAuth />
              </ProtectedRoute>
            }
          />

          <Route
            path="/admin/screener-config"
            element={
              <ProtectedRoute requireAdmin={true}>
                <AdminScreenerConfig />
              </ProtectedRoute>
            }
          />

          <Route
            path="/admin/users"
            element={
              <ProtectedRoute requireAdmin={true}>
                <AdminUsers />
              </ProtectedRoute>
            }
          />

          {/* Catch-all route */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
