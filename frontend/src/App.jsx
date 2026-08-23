import React, { useState, useEffect, useCallback } from 'react';
import Navbar from './components/Navbar';
import ToastContainer from './components/Toast';
import AdminModal from './components/AdminModal';
import HomePage from './pages/HomePage';
import YouTubePage from './pages/YouTubePage';
import AdminPage from './pages/AdminPage';
import { fetchAuthStatus, fetchTasks, subscribeToTaskEvents } from './services/api';

export default function App() {
  const [currentPage, setCurrentPage] = useState('home'); // 'home' | 'youtube' | 'admin'
  const [isDark, setIsDark] = useState(true);
  const [authStatus, setAuthStatus] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [isAdminModalOpen, setIsAdminModalOpen] = useState(false);
  const [toasts, setToasts] = useState([]);

  // Theme Sync
  useEffect(() => {
    if (isDark) {
      document.body.className = 'dark-theme';
    } else {
      document.body.className = 'light-theme';
    }
  }, [isDark]);

  const addToast = (message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      removeToast(id);
    }, 4000);
  };

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const refreshAuth = useCallback(async () => {
    try {
      const data = await fetchAuthStatus();
      setAuthStatus(data);
    } catch (e) {
      console.error('Failed to load auth status', e);
    }
  }, []);

  const refreshTasks = useCallback(async () => {
    try {
      const data = await fetchTasks();
      setTasks(data.tasks || []);
    } catch (e) {
      console.error('Failed to load tasks', e);
    }
  }, []);

  // Initial Load
  useEffect(() => {
    refreshAuth();
    refreshTasks();
  }, [refreshAuth, refreshTasks]);

  // Real-time SSE Subscription
  useEffect(() => {
    const unsubscribe = subscribeToTaskEvents((update) => {
      setTasks((prevTasks) => {
        const index = prevTasks.findIndex((t) => t.id === update.task_id);
        if (index >= 0) {
          const updated = [...prevTasks];
          updated[index] = {
            ...updated[index],
            ...update,
            status: update.status,
            progress_percent: update.progress_percent,
            download_speed: update.download_speed,
            eta: update.eta,
            download_url: update.status === 'completed' ? `/api/downloads/${update.task_id}/file` : updated[index].download_url
          };
          return updated;
        } else {
          // New task created elsewhere or pushed
          return [
            {
              id: update.task_id,
              user_id: authStatus?.user_id || 'me',
              service_type: 'youtube',
              media_type: 'video',
              url: update.title || 'YouTube Media',
              title: update.title,
              thumbnail_url: update.thumbnail_url,
              status: update.status,
              progress_percent: update.progress_percent,
              created_at: new Date().toISOString(),
              download_url: update.status === 'completed' ? `/api/downloads/${update.task_id}/file` : null
            },
            ...prevTasks
          ];
        }
      });

      // If finished, refresh quota counter
      if (update.status === 'completed' || update.status === 'failed' || update.status === 'cancelled') {
        refreshAuth();
      }
    });

    return () => {
      unsubscribe();
    };
  }, [authStatus?.user_id, refreshAuth]);

  return (
    <div className="app-container">
      <Navbar
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
        isDark={isDark}
        setIsDark={setIsDark}
        authStatus={authStatus}
        onOpenAdminModal={() => setIsAdminModalOpen(true)}
      />

      <main style={{ flex: 1 }}>
        {currentPage === 'home' && (
          <HomePage
            onSelectService={(service) => {
              if (service === 'youtube') setCurrentPage('youtube');
            }}
            addToast={addToast}
          />
        )}

        {currentPage === 'youtube' && (
          <YouTubePage
            tasks={tasks}
            refreshTasks={refreshTasks}
            refreshAuth={refreshAuth}
            authStatus={authStatus}
            addToast={addToast}
          />
        )}

        {currentPage === 'admin' && (
          <AdminPage
            tasks={tasks}
            refreshTasks={refreshTasks}
            refreshAuth={refreshAuth}
            addToast={addToast}
            onNavigateHome={() => setCurrentPage('home')}
          />
        )}
      </main>

      {/* Admin Login Dialog */}
      <AdminModal
        isOpen={isAdminModalOpen}
        onClose={() => setIsAdminModalOpen(false)}
        authStatus={authStatus}
        refreshAuth={refreshAuth}
        addToast={addToast}
        navigateToAdmin={() => setCurrentPage('admin')}
      />

      {/* Toast Notifications */}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </div>
  );
}
