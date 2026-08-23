import React, { useState } from 'react';
import { Shield, X, Key, LogOut, LayoutDashboard } from 'lucide-react';
import { adminLogin, adminLogout } from '../services/api';

export default function AdminModal({
  isOpen,
  onClose,
  authStatus,
  refreshAuth,
  addToast,
  navigateToAdmin
}) {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!password) return;
    setLoading(true);
    try {
      await adminLogin(password);
      addToast('管理员登录成功 (会话保持 7 天)', 'success');
      setPassword('');
      await refreshAuth();
      onClose();
      navigateToAdmin();
    } catch (err) {
      addToast(err.message || '密码错误', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    setLoading(true);
    try {
      await adminLogout();
      addToast('已成功退出管理员登录', 'success');
      await refreshAuth();
      onClose();
    } catch (err) {
      addToast('退出失败', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, fontSize: '1.15rem' }}>
            <Shield size={20} color="#6366f1" />
            <span>{authStatus?.is_admin ? '管理员身份' : '管理员登录'}</span>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={18} />
          </button>
        </div>

        {authStatus?.is_admin ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              当前已作为管理员登录，享有无限下载配额及系统控制权限。
            </p>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
              <button
                className="btn-primary"
                style={{ flex: 1, padding: '0.75rem' }}
                onClick={() => {
                  onClose();
                  navigateToAdmin();
                }}
              >
                <LayoutDashboard size={16} />
                <span>进入管理控制台</span>
              </button>
              <button
                className="btn-cancel"
                style={{ padding: '0.75rem 1rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}
                onClick={handleLogout}
                disabled={loading}
              >
                <LogOut size={16} />
                <span>退出</span>
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              请输入系统管理员密码。登录后将免除每日下载次数限制。
            </p>
            <div style={{ position: 'relative' }}>
              <input
                type="password"
                className="url-input"
                style={{ width: '100%', paddingLeft: '2.5rem' }}
                placeholder="管理员密码"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoFocus
              />
              <Key size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '0.9rem', top: '50%', transform: 'translateY(-50%)' }} />
            </div>
            <button
              type="submit"
              className="btn-primary"
              style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}
              disabled={loading || !password}
            >
              {loading ? '正在验证...' : '确认登录'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
