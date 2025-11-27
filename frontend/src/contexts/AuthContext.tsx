import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { jwtDecode } from 'jwt-decode';

interface User {
  id: string;
  email: string | null;
  role: string;
  is_expert: boolean;
  auth_provider: 'google' | 'github' | 'orcid' | 'guest';
  orcid_id: string | null;
  display_name: string;
}

// The decoded JWT payload will have 'sub' for user ID.
interface DecodedToken {
  sub: string;
  email?: string;
  role?: string;
  is_expert?: boolean;
  auth_provider?: 'google' | 'github' | 'orcid';
  orcid_id?: string;
  display_name?: string;
  exp: number;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isGuest: boolean;
  isExpert: boolean;
  isLoading: boolean;
  logout: () => void;
  continueAsGuest: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGuest, setIsGuest] = useState(false);

  useEffect(() => {
    const processToken = (jwt: string) => {
      try {
        const decoded = jwtDecode<DecodedToken>(jwt);

        // Check if token is expired
        if (decoded.exp * 1000 < Date.now()) {
          localStorage.removeItem('auth_token');
          return;
        }

        const userInfo: User = {
          id: decoded.sub,
          email: decoded.email || null,
          role: decoded.role || 'viewer',
          is_expert: decoded.is_expert || false,
          auth_provider: decoded.auth_provider || 'google',
          orcid_id: decoded.orcid_id || null,
          display_name: decoded.display_name || 'User',
        };

        setToken(jwt);
        setUser(userInfo);
        setIsGuest(false);
        localStorage.setItem('auth_token', jwt);
        localStorage.removeItem('is_guest');

      } catch (error) {
        console.error("Failed to decode token:", error);
        localStorage.removeItem('auth_token');
      }
    };
    
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get('token');

    if (urlToken) {
      processToken(urlToken);
      // Clean up the URL
      window.history.replaceState({}, document.title, window.location.pathname);
    } else {
      const storedToken = localStorage.getItem('auth_token');
      if (storedToken) {
        processToken(storedToken);
      } else if (localStorage.getItem('is_guest') === 'true') {
        setIsGuest(true);
      }
    }
    setIsLoading(false);
  }, []);

  const continueAsGuest = async () => {
    const response = await fetch(`${API_BASE_URL}/api/oauth/guest`, {
        method: 'POST'
    });
    if (!response.ok) {
        throw new Error("Failed to create guest session");
    }
    const data = await response.json();
    const guestToken = data.access_token;
    
    setToken(guestToken);
    setUser(null); // Or a guest user object if you prefer
    setIsGuest(true);
    localStorage.setItem('auth_token', guestToken);
    localStorage.setItem('is_guest', 'true');
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    setIsGuest(false);
    localStorage.removeItem('auth_token');
    localStorage.removeItem('is_guest');
    // Reload to ensure all state is cleared
    window.location.href = '/'; 
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !isGuest,
        isGuest,
        isExpert: user?.is_expert || false,
        isLoading,
        logout,
        continueAsGuest,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
