import React, { useState, useEffect } from 'react';
import { 
  Settings, 
  X, 
  Server, 
  Key, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Zap, 
  Shield, 
  Eye, 
  EyeOff, 
  Save, 
  HelpCircle,
  Cpu
} from 'lucide-react';
import { 
  fetchAppleMusicSettings, 
  saveAppleMusicSettings, 
  testWrapperConnection 
} from '../services/api';

export default function SettingsModal({
  isOpen,
  onClose,
  authStatus,
  onOpenAdminLogin,
  addToast
}) {
  const [wrapperIp, setWrapperIp] = useState('');
  const [mediaUserToken, setMediaUserToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [loadingConfig, setLoadingConfig] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null); // { online: bool, message: str }

  useEffect(() => {
    if (isOpen) {
      loadCurrentConfig();
      setTestResult(null);
    }
  }, [isOpen]);

  const loadCurrentConfig = async () => {
    setLoadingConfig(true);
    try {
      const data = await fetchAppleMusicSettings();
      if (data) {
        setWrapperIp(data.wrapper_ip || '');
        setMediaUserToken(data.media_user_token || '');
      }
    } catch (err) {
      console.warn('获取设置失败 (可能未登录管理员)', err);
    } finally {
      setLoadingConfig(false);
    }
  };

  if (!isOpen) return null;

  const handleTestConnection = async () => {
    if (!wrapperIp.trim()) {
      addToast('请先输入 Wrapper 服务端 IP', 'error');
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const res = await testWrapperConnection(wrapperIp.trim());
      setTestResult(res);
      if (res.online) {
        addToast(res.message, 'success');
      } else {
        addToast(res.message, 'error');
      }
    } catch (err) {
      setTestResult({
        online: false,
        message: err.message || '测试连接失败'
      });
      addToast(err.message || '测试连接失败', 'error');
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async (e) => {
    if (e) e.preventDefault();
    if (!authStatus?.is_admin) {
      addToast('保存配置需要管理员权限，请先登录', 'error');
      return;
    }
    setSaving(true);
    try {
      await saveAppleMusicSettings(wrapperIp.trim(), mediaUserToken.trim());
      addToast('Apple Music & Wrapper 配置已更新并自动写入 config.yaml', 'success');
      onClose();
    } catch (err) {
      addToast(err.message || '保存配置失败', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div 
        className="modal-card" 
        style={{ maxWidth: '520px', width: '100%' }} 
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', fontWeight: 800, fontSize: '1.2rem' }}>
            <div style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#6366f1', padding: '0.4rem', borderRadius: 'var(--radius-sm)', display: 'flex' }}>
              <Settings size={20} />
            </div>
            <span>服务配置 / Settings</span>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '0.2rem' }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Admin status notice */}
        {!authStatus?.is_admin && (
          <div style={{ 
            background: 'rgba(245, 158, 11, 0.1)', 
            border: '1px solid rgba(245, 158, 11, 0.3)', 
            borderRadius: 'var(--radius-sm)', 
            padding: '0.75rem 1rem', 
            marginBottom: '1.25rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '0.6rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: '#f59e0b', flex: 1, minWidth: '180px' }}>
              <Shield size={16} style={{ flexShrink: 0 }} />
              <span>当前为只读模式。修改服务配置需要管理员权限。</span>
            </div>
            {onOpenAdminLogin && (
              <button 
                type="button"
                className="btn-primary"
                style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem', whiteSpace: 'nowrap', flexShrink: 0 }}
                onClick={() => {
                  onClose();
                  onOpenAdminLogin();
                }}
              >
                管理员登录
              </button>
            )}
          </div>
        )}

        {loadingConfig ? (
          <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
            <RefreshCw size={24} className="spin" style={{ margin: '0 auto 0.5rem', display: 'block' }} />
            <span>正在读取已有 config.yaml 配置...</span>
          </div>
        ) : (
          <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1.15rem' }}>
            
            {/* 1. Wrapper Server IP Section */}
            <div className="settings-card-section">
              <div className="settings-section-header">
                <label style={{ fontWeight: 700, fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-primary)' }}>
                  <Server size={16} color="#fa233b" style={{ flexShrink: 0 }} />
                  <span>Apple Music Wrapper 服务端 IP</span>
                </label>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  自动配置 10020 / 20020
                </span>
              </div>

              <div className="settings-ip-group">
                <input
                  type="text"
                  className="url-input"
                  placeholder="例如: 192.168.3.154"
                  value={wrapperIp}
                  onChange={(e) => {
                    setWrapperIp(e.target.value);
                    setTestResult(null);
                  }}
                  disabled={!authStatus?.is_admin || saving}
                />

                <button
                  type="button"
                  className="btn-cancel settings-test-btn"
                  onClick={handleTestConnection}
                  disabled={testing || !wrapperIp.trim()}
                  title="探测 Wrapper 服务的 10020 端口连通性"
                >
                  {testing ? (
                    <>
                      <RefreshCw size={14} className="spin" />
                      <span>探测中...</span>
                    </>
                  ) : (
                    <>
                      <Zap size={14} color="#6366f1" />
                      <span>测试连接</span>
                    </>
                  )}
                </button>
              </div>

              {/* Test result status bar */}
              {testResult && (
                <div style={{ 
                  marginTop: '0.6rem', 
                  fontSize: '0.8rem', 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '0.4rem',
                  color: testResult.online ? '#10b981' : '#ef4444',
                  background: testResult.online ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)',
                  padding: '0.4rem 0.6rem',
                  borderRadius: 'var(--radius-sm)'
                }}>
                  {testResult.online ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
                  <span>{testResult.message}</span>
                </div>
              )}

              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.5rem', lineHeight: 1.4 }}>
                💡 仅需输入 Wrapper 服务所在的局域网设备 IP，系统将自动映射并写入 <code>decrypt-m3u8-port</code> 与 <code>get-m3u8-port</code>。
              </div>
            </div>

            {/* 2. Apple Music Media-User-Token Section */}
            <div className="settings-card-section">
              <div className="settings-section-header">
                <label style={{ fontWeight: 700, fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-primary)' }}>
                  <Key size={16} color="#6366f1" style={{ flexShrink: 0 }} />
                  <span>Media-User-Token (凭据)</span>
                </label>

                <button
                  type="button"
                  onClick={() => setShowToken(!showToken)}
                  style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', padding: '0.2rem 0', flexShrink: 0 }}
                >
                  {showToken ? <EyeOff size={13} /> : <Eye size={13} />}
                  <span>{showToken ? '隐藏' : '显示'}</span>
                </button>
              </div>

              <textarea
                className="url-input"
                style={{ 
                  width: '100%', 
                  padding: '0.65rem 0.85rem', 
                  fontSize: '0.85rem',
                  minHeight: '68px',
                  resize: 'vertical',
                  fontFamily: showToken ? 'var(--font-mono)' : 'inherit',
                  boxSizing: 'border-box'
                }}
                placeholder="粘贴你的 media-user-token (以 0. 开头的 Base64 凭据，若仅下载 ALAC 免 Token 则可留空)"
                value={showToken ? mediaUserToken : (mediaUserToken ? '••••••••••••••••••••••••••••••••••••••••••••••••' : '')}
                onChange={(e) => setMediaUserToken(e.target.value)}
                onFocus={() => setShowToken(true)}
                disabled={!authStatus?.is_admin || saving}
              />

              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.5rem', lineHeight: 1.4 }}>
                ℹ️ 用于获取 AAC-LC 音频流与同步逐字歌词。若你已在 <code>config.yaml</code> 中填入，系统会自动同步展示。
              </div>
            </div>

            {/* Actions Footer */}
            <div className="settings-footer">
              <button
                type="button"
                className="btn-cancel"
                onClick={onClose}
                disabled={saving}
              >
                取消
              </button>

              {authStatus?.is_admin && (
                <button
                  type="submit"
                  className="btn-primary settings-save-btn"
                  disabled={saving}
                >
                  {saving ? (
                    <>
                      <RefreshCw size={15} className="spin" />
                      <span>正在保存...</span>
                    </>
                  ) : (
                    <>
                      <Save size={15} />
                      <span>保存并应用配置</span>
                    </>
                  )}
                </button>
              )}
            </div>

          </form>
        )}

      </div>
    </div>
  );
}
