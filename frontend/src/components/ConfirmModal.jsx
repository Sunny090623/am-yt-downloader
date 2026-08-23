import React, { useState } from 'react';
import { AlertTriangle, X, Trash2 } from 'lucide-react';

export default function ConfirmModal({
  isOpen,
  title = '确认操作',
  message = '确定要执行此操作吗？',
  confirmText = '确认删除',
  confirmColor = '#ef4444',
  onConfirm,
  onCancel,
  showDontAskAgain = true
}) {
  const [dontAskAgain, setDontAskAgain] = useState(false);

  if (!isOpen) return null;

  const handleConfirm = () => {
    onConfirm(dontAskAgain);
    setDontAskAgain(false);
  };

  const handleCancel = () => {
    onCancel();
    setDontAskAgain(false);
  };

  return (
    <div className="modal-overlay" onClick={handleCancel}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '420px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, fontSize: '1.15rem' }}>
            <AlertTriangle size={20} color={confirmColor} />
            <span>{title}</span>
          </div>
          <button
            onClick={handleCancel}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
          >
            <X size={18} />
          </button>
        </div>

        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '1.25rem' }}>
          {message}
        </p>

        {showDontAskAgain && (
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)', cursor: 'pointer', marginBottom: '1.5rem', userSelect: 'none' }}>
            <input
              type="checkbox"
              checked={dontAskAgain}
              onChange={(e) => setDontAskAgain(e.target.checked)}
              style={{ accentColor: 'var(--accent-primary)', width: '15px', height: '15px', cursor: 'pointer' }}
            />
            <span>以后不再提示</span>
          </label>
        )}

        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
          <button
            className="btn-cancel"
            style={{ padding: '0.6rem 1.2rem', fontSize: '0.9rem' }}
            onClick={handleCancel}
          >
            取消
          </button>
          <button
            style={{
              background: confirmColor === '#ef4444' ? 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)' : 'var(--accent-gradient)',
              color: 'white',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              padding: '0.6rem 1.25rem',
              fontSize: '0.9rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              boxShadow: '0 4px 12px rgba(239, 68, 68, 0.3)'
            }}
            onClick={handleConfirm}
          >
            <Trash2 size={15} />
            <span>{confirmText}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
