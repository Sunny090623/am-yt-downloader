import React, { useState } from 'react';
import { Music, Download, Link2, RefreshCw, ListOrdered, Sparkles, Trash2, Disc, Layers, Settings } from 'lucide-react';
import TaskCard from '../components/TaskCard';
import ConfirmModal from '../components/ConfirmModal';
import { createDownloadTask, deleteTask, clearFinishedTasks } from '../services/api';

export default function AppleMusicPage({
  tasks,
  refreshTasks,
  refreshAuth,
  authStatus,
  addToast,
  onOpenSettings
}) {

  const [url, setUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [confirmModal, setConfirmModal] = useState({
    isOpen: false,
    type: 'single', // 'single' | 'clear_all'
    targetTask: null,
    title: '',
    message: ''
  });

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!url.trim()) return;

    setSubmitting(true);
    try {
      await createDownloadTask(url.trim(), 'apple_music');
      addToast('Apple Music 下载任务已提交，正在排队处理', 'success');
      setUrl('');
      await refreshTasks();
      await refreshAuth();
    } catch (err) {
      addToast(err.message || '提交失败', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRetry = (retryUrl) => {
    setUrl(retryUrl);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Single Task Deletion Trigger
  const handleRequestDelete = (task) => {
    const skipConfirm = localStorage.getItem('skip_delete_confirm') === 'true';
    if (skipConfirm) {
      executeDeleteSingle(task.id);
    } else {
      setConfirmModal({
        isOpen: true,
        type: 'single',
        targetTask: task,
        title: '删除任务与文件',
        message: `确定要删除任务 “${task.title || task.url}” 及其对应的本地下载文件吗？`
      });
    }
  };

  const executeDeleteSingle = async (taskId) => {
    try {
      await deleteTask(taskId);
      addToast('任务及已下载文件已彻底删除', 'success');
      await refreshTasks();
    } catch (err) {
      addToast(err.message || '删除失败', 'error');
    }
  };

  // Batch Clear-All Trigger
  const handleClearAllClick = () => {
    const skipConfirm = localStorage.getItem('skip_clear_all_confirm') === 'true';
    if (skipConfirm) {
      executeClearAll();
    } else {
      setConfirmModal({
        isOpen: true,
        type: 'clear_all',
        targetTask: null,
        title: '一键清除已完成任务',
        message: '确定要清除所有已完成、失败或取消的历史任务及其本地文件吗？正在进行的下载不会受影响。'
      });
    }
  };

  const executeClearAll = async () => {
    try {
      const res = await clearFinishedTasks('apple_music');
      addToast(res.message || '已清理所有历史任务及文件', 'success');
      await refreshTasks();
    } catch (err) {
      addToast(err.message || '一键清除失败', 'error');
    }
  };


  // Handle Modal Confirmation
  const handleModalConfirm = (dontAskAgain) => {
    if (confirmModal.type === 'single') {
      if (dontAskAgain) {
        localStorage.setItem('skip_delete_confirm', 'true');
      }
      if (confirmModal.targetTask) {
        executeDeleteSingle(confirmModal.targetTask.id);
      }
    } else if (confirmModal.type === 'clear_all') {
      if (dontAskAgain) {
        localStorage.setItem('skip_clear_all_confirm', 'true');
      }
      executeClearAll();
    }
    setConfirmModal((prev) => ({ ...prev, isOpen: false }));
  };

  const handleModalCancel = () => {
    setConfirmModal((prev) => ({ ...prev, isOpen: false }));
  };

  // Filter tasks for Apple Music service
  const appleMusicTasks = tasks.filter((t) => t.service_type === 'apple_music');
  const finishedTasksCount = appleMusicTasks.filter((t) =>
    ['completed', 'failed', 'cancelled', 'interrupted', 'expired'].includes(t.status)
  ).length;

  return (
    <div>
      {/* Title & Quota Banner */}
      <div style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div style={{ background: 'linear-gradient(135deg, #fa233b 0%, #fb5c74 100%)', width: '32px', height: '32px', borderRadius: 'var(--radius-sm)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', boxShadow: '0 4px 12px rgba(250, 35, 59, 0.3)' }}>
            <Music size={20} />
          </div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 800 }}>Apple Music Downloader</h2>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          {!authStatus?.is_admin && authStatus?.quota && (
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              今日剩余额度: 专辑 <strong style={{ color: 'var(--text-primary)' }}>{authStatus.quota.album_remaining}</strong>/{authStatus.quota.album_limit} 张 &nbsp;•&nbsp; 单曲 (Single) <strong style={{ color: 'var(--text-primary)' }}>{authStatus.quota.single_remaining}</strong>/{authStatus.quota.single_limit} 首
            </span>
          )}

          {onOpenSettings && (

            <button
              className="btn-cancel"
              style={{ padding: '0.35rem 0.65rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
              onClick={onOpenSettings}
              title="配置 Wrapper 服务端 IP 与 Token"
            >
              <Settings size={14} color="#fa233b" />
              <span>Wrapper 配置</span>
            </button>
          )}
        </div>
      </div>


      {/* Input Box on the Same Page */}
      <div className="download-input-container">
        <form onSubmit={handleSubmit} className="input-group">
          <div style={{ position: 'relative', flex: 1 }}>
            <input
              type="text"
              className="url-input"
              style={{ width: '100%', paddingLeft: '2.5rem' }}
              placeholder="在此粘贴 Apple Music 歌曲或专辑链接 (如: https://music.apple.com/.../album/... 或 /song/...)"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={submitting}
              autoFocus
            />
            <Link2 size={18} color="var(--text-muted)" style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)' }} />
          </div>

          <button
            type="submit"
            className="btn-primary"
            style={{ background: 'linear-gradient(135deg, #fa233b 0%, #d81b30 100%)' }}
            disabled={submitting || !url.trim()}
          >
            {submitting ? (
              <>
                <RefreshCw size={18} className="spin" />
                <span>正在解析...</span>
              </>
            ) : (
              <>
                <Download size={18} />
                <span>立即下载</span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* Task List Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, fontSize: '1.1rem' }}>
          <ListOrdered size={20} color="var(--primary)" />
          <span>下载任务列表 ({appleMusicTasks.length})</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {finishedTasksCount > 0 && (
            <button
              className="btn-cancel"
              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.75rem', fontSize: '0.85rem' }}
              onClick={handleClearAllClick}
              title="清除所有已完成、失败或取消的任务记录与文件"
            >
              <Trash2 size={14} color="#ef4444" />
              <span>一键清除已完成 ({finishedTasksCount})</span>
            </button>
          )}

          <button
            className="btn-cancel"
            style={{ padding: '0.4rem 0.65rem' }}
            onClick={() => {
              refreshTasks();
              refreshAuth();
              addToast('已刷新任务与额度状态', 'info');
            }}
            title="刷新列表"
          >
            <RefreshCw size={15} />
          </button>
        </div>
      </div>

      {/* Tasks Grid */}
      {appleMusicTasks.length === 0 ? (
        <div
          style={{
            textAlign: 'center',
            padding: '3.5rem 1rem',
            background: 'var(--bg-card)',
            borderRadius: 'var(--radius-lg)',
            border: '1px dashed var(--border-color)',
            color: 'var(--text-muted)'
          }}
        >
          <Music size={40} style={{ opacity: 0.3, marginBottom: '0.75rem' }} />
          <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-secondary)' }}>暂无 Apple Music 下载任务</div>
          <div style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>输入上方链接即可开始下载单曲或整张专辑</div>
        </div>
      ) : (
        <div className="task-list">
          {appleMusicTasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onRetry={handleRetry}
              onRequestDelete={handleRequestDelete}
              addToast={addToast}
            />
          ))}
        </div>
      )}

      {/* Confirmation Modal */}
      <ConfirmModal
        isOpen={confirmModal.isOpen}
        title={confirmModal.title}
        message={confirmModal.message}
        onConfirm={handleModalConfirm}
        onCancel={handleModalCancel}
      />
    </div>
  );
}
