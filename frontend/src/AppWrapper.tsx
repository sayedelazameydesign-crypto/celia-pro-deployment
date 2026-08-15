/**
 * App Wrapper Component
 * Handles authentication routing with lazy loading (code splitting)
 * 
 * Performance Optimization (P2-6):
 * - Route-based code splitting with React.lazy
 * - Each page loads only when needed
 * - Suspense fallback provides loading state during chunk download
 */

import React, { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'

// Lazy-loaded pages - each becomes a separate JS chunk
// These are only loaded when the user navigates to the corresponding route
const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const App = lazy(() => import('./App'))

/**
 * Loading fallback component
 * Displayed while a lazy-loaded chunk is being downloaded
 */
const LoadingFallback: React.FC = () => (
  <div style={{ 
    display: 'flex', 
    alignItems: 'center', 
    justifyContent: 'center', 
    height: '100vh',
    background: '#0a0a1a',
    color: 'white',
    fontFamily: 'Inter, system-ui, sans-serif',
  }}>
    <div style={{ textAlign: 'center' }}>
      {/* Animated spinner */}
      <div style={{
        width: '40px',
        height: '40px',
        margin: '0 auto 16px',
        border: '3px solid rgba(34, 211, 238, 0.2)',
        borderTopColor: '#22d3ee',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
      <p style={{ color: '#9ca3af', fontSize: '14px' }}>Loading...</p>
    </div>
  </div>
)

const AppWrapper: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return <LoadingFallback />
  }

  return (
    <Suspense fallback={<LoadingFallback />}>
      <Routes>
        <Route 
          path="/login" 
          element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />} 
        />
        <Route 
          path="/register" 
          element={isAuthenticated ? <Navigate to="/" replace /> : <RegisterPage />} 
        />
        <Route 
          path="/*" 
          element={isAuthenticated ? <App /> : <Navigate to="/login" replace />} 
        />
      </Routes>
    </Suspense>
  )
}

export default AppWrapper
