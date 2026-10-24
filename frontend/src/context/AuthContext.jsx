import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('alphaquant_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [brokerSession, setBrokerSession] = useState({
    authenticated: false,
    client_id: null,
    market_open: false,
    loading: true,
  });

  const checkBrokerStatus = async () => {
    try {
      const res = await api.get('/auth/session-status');
      setBrokerSession({
        authenticated: res.data.authenticated,
        client_id: res.data.client_id,
        market_open: res.data.market_open,
        last_updated: res.data.last_updated,
        loading: false,
      });
    } catch (err) {
      setBrokerSession((prev) => ({ ...prev, loading: false }));
    }
  };

  useEffect(() => {
    checkBrokerStatus();
    const interval = setInterval(checkBrokerStatus, 30000); // 30s status polling
    return () => clearInterval(interval);
  }, []);

  const login = async (username, password) => {
    const res = await api.post('/auth/login', { username, password });
    const { access_token, role } = res.data;
    const userData = { username, role };
    localStorage.setItem('alphaquant_token', access_token);
    localStorage.setItem('alphaquant_user', JSON.stringify(userData));
    setUser(userData);
    await checkBrokerStatus();
    return userData;
  };

  const logout = () => {
    localStorage.removeItem('alphaquant_token');
    localStorage.removeItem('alphaquant_user');
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        logout,
        brokerSession,
        refreshBrokerStatus: checkBrokerStatus,
        isAdmin: user?.role === 'admin',
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
