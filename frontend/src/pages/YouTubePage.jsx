import React, { useState } from 'react';
import { Youtube, Download, Link2, RefreshCw, ListOrdered, Sparkles, Trash2 } from 'lucide-react';
import TaskCard from '../components/TaskCard';
import ConfirmModal from '../components/ConfirmModal';
import { createDownloadTask, deleteTask, clearFinishedTasks } from '../services/api';

export default function YouTubePage({
  tasks,
  refreshTasks,
  refreshAuth,
  authStatus,
  addToast
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
      await createDownloadTask(url.trim(), 'youtube');
      addToast('下载任务已提交，正在开始下载', 'success');
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
      const res = await clearFinishedTasks('youtube');
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
    setConfirmModal(prev => ({ ...prev, isOpen: false }));
  };

  const youtubeTasks = tasks.filter(t => !t.service_type || t.service_type === 'youtube');
  const activeTasks = youtubeTasks.filter(t => ['queued', 'fetching_info', 'downloading', 'processing'].includes(t.status));
  const finishedTasks = youtubeTasks.filter(t => !['queued', 'fetching_info', 'downloading', 'processing'].includes(t.status));

  return (
    <div>
      {/* Title & Quota Banner */}
      <div style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div style={{ background: 'var(--yt-gradient)', width: '32px', height: '32px', borderRadius: 'var(--radius-sm)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white' }}>
            <Youtube size={20} />
          </div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 800 }}>YouTube Downloader</h2>
        </div>

        {!authStatus?.is_admin && authStatus?.quota && (
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            今日剩余额度: <strong style={{ color: 'var(--text-primary)' }}>{authStatus.quota.video_remaining}</strong> / {authStatus.quota.video_limit} 视频
          </span>
        )}
      </div>


      {/* Input Box on the Same Page */}
      <div className="download-input-container">
        <form onSubmit={handleSubmit} className="input-group">
          <div style={{ position: 'relative', flex: 1 }}>
            <input
              type="text"
              className="url-input"
              style={{ width: '100%', paddingLeft: '2.5rem' }}
              placeholder="在此粘贴 YouTube 视频链接 (如: https://www.youtube.com/watch?v=... 或 https://youtu.be/...)"
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

      {/* Download Tasks List */}
      <div className="tasks-section">
        <div className="section-title-bar">
          <div className="section-title">
            <ListOrdered size={18} />
            <span>下载任务列表 ({youtubeTasks.length})</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            {finishedTasks.length > 0 && (
              <button
                className="icon-btn"
                style={{ width: 'auto', padding: '0 0.85rem', height: '32px', fontSize: '0.825rem', display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--text-secondary)' }}
                onClick={handleClearAllClick}
                title="一键清除所有已完成、失败及历史任务"
              >
                <Trash2 size={14} color="#ef4444" />
                <span>一键清除</span>
              </button>
            )}

            <button
              className="icon-btn"
              style={{ width: '32px', height: '32px' }}
              onClick={refreshTasks}
              title="刷新任务列表"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {youtubeTasks.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3.5rem 1rem', background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', border: '1px dashed var(--border-subtle)' }}>
            <Sparkles size={36} color="var(--text-muted)" style={{ margin: '0 auto 1rem', display: 'block', opacity: 0.6 }} />
            <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>暂无下载任务</div>
            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
              粘贴 YouTube 视频链接后点击“立即下载”，任务将实时在此处流式展示。
            </div>
          </div>
        ) : (

          <>
            {/* Active Running Tasks */}
            {activeTasks.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                onRetry={handleRetry}
                onRequestDelete={handleRequestDelete}
                onDelete={refreshTasks}
                addToast={addToast}
              />
            ))}

            {/* Completed / History Tasks */}
            {finishedTasks.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                onRetry={handleRetry}
                onRequestDelete={handleRequestDelete}
                onDelete={refreshTasks}
                addToast={addToast}
              />
            ))}
          </>
        )}
      </div>

      {/* Reusable Confirmation Dialog with "Don't ask again" */}
      <ConfirmModal
        isOpen={confirmModal.isOpen}
        title={confirmModal.title}
        message={confirmModal.message}
        onConfirm={handleModalConfirm}
        onCancel={() => setConfirmModal(prev => ({ ...prev, isOpen: false }))}
      />
    </div>
  );
}
