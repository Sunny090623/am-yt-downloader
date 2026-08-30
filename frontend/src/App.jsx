import React, { useState, useEffect, useCallback } from 'react';
import Navbar from './components/Navbar';
import ToastContainer from './components/Toast';
import AdminModal from './components/AdminModal';
import SettingsModal from './components/SettingsModal';
import HomePage from './pages/HomePage';
import YouTubePage from './pages/YouTubePage';
import AppleMusicPage from './pages/AppleMusicPage';
import AdminPage from './pages/AdminPage';
import { fetchAuthStatus, fetchTasks, subscribeToTaskEvents } from './services/api';

export default function App() {
  const [currentPage, setCurrentPage] = useState('home'); // 'home' | 'youtube' | 'apple_music' | 'admin'
  const [isDark, setIsDark] = useState(() => {
    try {
      const saved = localStorage.getItem('amyt_theme');
      if (saved !== null) {
        return saved === 'dark';
      }
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
        return false;
      }
    } catch (e) {}
    return true;
  });
  const [authStatus, setAuthStatus] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [isAdminModalOpen, setIsAdminModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [toasts, setToasts] = useState([]);

  // Theme Sync & Persistence
  useEffect(() => {
    if (isDark) {
      document.body.className = 'dark-theme';
      try {
        localStorage.setItem('amyt_theme', 'dark');
      } catch (e) {}
    } else {
      document.body.className = 'light-theme';
      try {
        localStorage.setItem('amyt_theme', 'light');
      } catch (e) {}
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
          const curr = updated[index];
          updated[index] = {
            ...curr,
            ...update,
            title: update.title || curr.title,
            thumbnail_url: update.thumbnail_url || curr.thumbnail_url,
            uploader: update.uploader || curr.uploader,
            duration: update.duration || curr.duration,
            status: update.status || curr.status,
            progress_percent: update.progress_percent !== undefined ? update.progress_percent : curr.progress_percent,
            download_speed: update.download_speed || curr.download_speed,
            eta: update.eta || curr.eta,
            file_name: update.file_name || curr.file_name,
            file_size: update.file_size || curr.file_size,
            download_url: update.status === 'completed' ? `/api/downloads/${update.task_id}/file` : curr.download_url
          };
          return updated;
        }
 else {
          // New task created elsewhere or pushed
          return [
            {
              id: update.task_id,
              user_id: authStatus?.user_id || 'me',
              service_type: update.service_type || 'youtube',
              media_type: update.media_type || (update.service_type === 'apple_music' ? 'single' : 'video'),
              url: update.title || (update.service_type === 'apple_music' ? 'Apple Music Audio' : 'Audio'),
              title: update.title || (update.service_type === 'apple_music' ? 'Apple Music Audio' : 'Audio'),
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
        onOpenSettings={() => setIsSettingsModalOpen(true)}
      />

      <main style={{ flex: 1 }}>
        {currentPage === 'home' && (
          <HomePage
            onSelectService={(service) => {
              if (service === 'youtube') setCurrentPage('youtube');
              if (service === 'apple_music') setCurrentPage('apple_music');
            }}
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

        {currentPage === 'apple_music' && (
          <AppleMusicPage
            tasks={tasks}
            refreshTasks={refreshTasks}
            refreshAuth={refreshAuth}
            authStatus={authStatus}
            addToast={addToast}
            onOpenSettings={() => setIsSettingsModalOpen(true)}
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

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
        authStatus={authStatus}
        onOpenAdminLogin={() => {
          setIsSettingsModalOpen(false);
          setIsAdminModalOpen(true);
        }}
        addToast={addToast}
      />

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
