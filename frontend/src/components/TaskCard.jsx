import React from 'react';
import { 
  Download, 
  Clock, 
  AlertCircle, 
  CheckCircle2, 
  XCircle, 
  RotateCw, 
  Trash2, 
  Film, 
  ExternalLink,
  Zap,
  Timer
} from 'lucide-react';
import { cancelDownloadTask, deleteTask } from '../services/api';

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let val = bytes;
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024;
    i++;
  }
  return `${val.toFixed(2)} ${units[i]}`;
}

function formatDuration(seconds) {
  if (!seconds) return '';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s < 10 ? '0' : ''}${s}`;
}

function formatExpiration(expiresAtStr) {
  if (!expiresAtStr) return '';
  try {
    const exp = new Date(expiresAtStr);
    const now = new Date();
    const diffHours = Math.max(0, Math.round((exp - now) / (1000 * 3600)));
    return `将在约 ${diffHours} 小时后自动清理`;
  } catch (e) {
    return '';
  }
}

export default function TaskCard({ task, onRetry, onDelete, onRequestDelete, addToast }) {
  const isCompleted = task.status === 'completed';
  const isDownloading = task.status === 'downloading';
  const isFetching = task.status === 'fetching_info';
  const isQueued = task.status === 'queued';
  const isProcessing = task.status === 'processing';
  const isFailed = task.status === 'failed';
  const isCancelled = task.status === 'cancelled';
  const isInterrupted = task.status === 'interrupted';
  const isExpired = task.status === 'expired';

  const handleCancel = async () => {
    try {
      await cancelDownloadTask(task.id);
      addToast('已取消下载任务', 'info');
    } catch (e) {
      addToast(e.message || '取消失败', 'error');
    }
  };

  const handleDeleteClick = () => {
    if (onRequestDelete) {
      onRequestDelete(task);
    } else {
      handleDirectDelete();
    }
  };

  const handleDirectDelete = async () => {
    try {
      await deleteTask(task.id);
      addToast('已删除下载文件及记录', 'success');
      if (onDelete) onDelete(task.id);
    } catch (e) {
      addToast(e.message || '删除失败', 'error');
    }
  };

  const getStatusText = () => {
    switch (task.status) {
      case 'queued': return '排队中';
      case 'fetching_info': return '解析元数据...';
      case 'downloading': return `下载中 ${task.progress_percent?.toFixed(1) || 0}%`;
      case 'processing': return '转码合并中...';
      case 'completed': return '下载完成';
      case 'failed': return '下载失败';
      case 'cancelled': return '已取消';
      case 'interrupted': return '意外中断';
      case 'expired': return '已过期清理';
      default: return task.status;
    }
  };

  return (
    <div className={`task-card ${task.status}`}>
      <div className="task-header">
        {task.thumbnail_url ? (
          <img src={task.thumbnail_url} alt={task.title || 'Thumbnail'} className="task-thumbnail" />
        ) : (
          <div className="task-thumbnail">
            <Film size={28} />
          </div>
        )}

        <div className="task-info">
          <div>
            <div className="task-title" title={task.title || task.url}>
              {task.title || task.url}
            </div>
            <div className="task-meta">
              {task.uploader && <span>{task.uploader}</span>}
              {task.duration ? <span>• {formatDuration(task.duration)}</span> : null}
              {task.file_size ? <span>• {formatBytes(task.file_size)}</span> : null}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.5rem' }}>
            <span className={`status-badge ${task.status}`}>
              {isCompleted && <CheckCircle2 size={12} />}
              {isDownloading && <Zap size={12} />}
              {isFailed && <AlertCircle size={12} />}
              {isCancelled && <XCircle size={12} />}
              {isQueued && <Clock size={12} />}
              <span>{getStatusText()}</span>
            </span>

            {(isDownloading || isFetching || isQueued) && (
              <button className="btn-cancel" onClick={handleCancel}>
                取消
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Progress Bar for Active Downloads */}
      {(isDownloading || isFetching || isProcessing) && (
        <div className="progress-container">
          <div className="progress-bar-bg">
            <div
              className="progress-bar-fill"
              style={{
                width: `${Math.min(100, Math.max(isFetching ? 8 : 2, task.progress_percent || 0))}%`
              }}
            />
          </div>
          <div className="progress-details">
            <span>
              {task.download_speed ? `⚡ ${task.download_speed}` : (isFetching ? '正在获取视频流...' : '准备下载...')}
            </span>
            <span>
              {task.eta ? `⏳ 剩余约 ${task.eta}` : `${task.progress_percent?.toFixed(1) || 0}%`}
            </span>
          </div>
        </div>
      )}

      {/* Error Message display */}
      {(isFailed || isInterrupted) && task.error_message && (
        <div style={{ fontSize: '0.8rem', color: '#f87171', background: 'rgba(239, 68, 68, 0.08)', padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)' }}>
          {task.error_message}
        </div>
      )}

      {/* Action Footer */}
      {(isCompleted || isFailed || isCancelled || isInterrupted || isExpired) && (
        <div className="task-actions">
          {isCompleted && task.download_url && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                <a
                  href={task.download_url}
                  download={task.file_name || 'video'}
                  className="btn-download-file"
                >
                  <Download size={16} />
                  <span>保存到本地 ({formatBytes(task.file_size)})</span>
                </a>

                <button
                  className="btn-cancel"
                  style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.55rem 0.85rem' }}
                  onClick={handleDeleteClick}
                  title="删除此视频文件及记录"
                >
                  <Trash2 size={14} color="#ef4444" />
                  <span>删除</span>
                </button>
              </div>

              {task.expires_at && (
                <div className="retention-hint" title="文件从完成起保留24小时">
                  <Timer size={13} />
                  <span>{formatExpiration(task.expires_at)}</span>
                </div>
              )}
            </>
          )}

          {(isFailed || isCancelled || isInterrupted) && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              {onRetry && (
                <button className="btn-primary" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }} onClick={() => onRetry(task.url)}>
                  <RotateCw size={14} />
                  <span>重新提交</span>
                </button>
              )}
              <button
                className="btn-cancel"
                style={{ padding: '0.5rem 0.75rem' }}
                onClick={handleDeleteClick}
                title="删除此任务记录"
              >
                <Trash2 size={14} color="#ef4444" />
              </button>
            </div>
          )}

          {isExpired && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                文件已保留满 24 小时并安全删除
              </span>
              <button
                className="btn-cancel"
                style={{ padding: '0.35rem 0.65rem' }}
                onClick={handleDeleteClick}
                title="清理记录"
              >
                <Trash2 size={13} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
