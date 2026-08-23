import React from 'react';
import { Download, Shield, Sun, Moon, LogIn, ArrowLeft } from 'lucide-react';

export default function Navbar({
  currentPage,
  setCurrentPage,
  isDark,
  setIsDark,
  authStatus,
  onOpenAdminModal
}) {
  return (
    <header className="navbar">
      <div className="brand" onClick={() => setCurrentPage('home')}>
        <div className="brand-icon">
          <Download size={20} />
        </div>
        <span>MediaHub</span>
      </div>

      <div className="nav-actions">
        {/* Quota / Role Indicator */}
        {authStatus?.is_admin ? (
          <div
            className="quota-pill admin-pill"
            style={{ cursor: 'pointer' }}
            onClick={() => setCurrentPage('admin')}
            title="点击进入管理员控制台"
          >
            <Shield size={14} />
            <span>管理员</span>
          </div>
        ) : (
          authStatus?.quota && (
            <div className="quota-pill" title="今日普通用户剩余视频下载额度">
              <span>今日剩余: <strong>{authStatus.quota.video_remaining}</strong>/{authStatus.quota.video_limit}</span>
            </div>
          )
        )}

        {/* Back button when inside a specific page */}
        {currentPage !== 'home' && (
          <button
            className="icon-btn"
            onClick={() => setCurrentPage('home')}
            title="返回服务列表"
          >
            <ArrowLeft size={18} />
          </button>
        )}

        {/* Theme Toggle */}
        <button
          className="icon-btn"
          onClick={() => setIsDark(!isDark)}
          title={isDark ? "切换为亮色模式" : "切换为暗色模式"}
        >
          {isDark ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        {/* Admin Login / Console Button */}
        <button
          className="icon-btn"
          onClick={onOpenAdminModal}
          title={authStatus?.is_admin ? "管理员设置" : "管理员登录"}
        >
          {authStatus?.is_admin ? <Shield size={18} color="#10b981" /> : <LogIn size={18} />}
        </button>
      </div>
    </header>
  );
}
