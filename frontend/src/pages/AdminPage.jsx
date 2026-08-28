import React, { useState, useEffect, useRef } from 'react';
import { 
  Shield, 
  HardDrive, 
  Cpu, 
  Trash2, 
  RefreshCw, 
  Activity, 
  CheckCircle, 
  AlertTriangle,
  Server,
  LogOut
} from 'lucide-react';
import { fetchAdminStats, triggerManualCleanup, deleteAdminTask, adminLogout, fetchAdminLogs } from '../services/api';

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

export default function AdminPage({
  tasks,
  refreshTasks,
  refreshAuth,
  addToast,
  onNavigateHome
}) {
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState('');
  const [loading, setLoading] = useState(true);
  const [cleaning, setCleaning] = useState(false);
  const logContainerRef = useRef(null);

  const loadStats = async () => {
    try {
      const data = await fetchAdminStats();
      setStats(data);
    } catch (e) {
      addToast(e.message || '获取管理数据失败', 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadLogs = async () => {
    try {
      const logText = await fetchAdminLogs();
      setLogs(logText);
    } catch (e) {
      console.error('Failed to load logs', e);
    }
  };

  useEffect(() => {
    loadStats();
    loadLogs();
  }, []);

  // Automatically scroll to the latest log line whenever logs update
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);


  const handleCleanup = async () => {
    setCleaning(true);
    try {
      const res = await triggerManualCleanup();
      addToast(res.message, 'success');
      await loadStats();
      await refreshTasks();
    } catch (e) {
      addToast(e.message || '清理失败', 'error');
    } finally {
      setCleaning(false);
    }
  };

  const handleDeleteTask = async (taskId) => {
    if (!window.confirm(`确定要强制删除任务 ${taskId} 及其对应存储文件吗？`)) return;
    try {
      await deleteAdminTask(taskId);
      addToast('任务及文件已删除', 'success');
      await refreshTasks();
      await loadStats();
    } catch (e) {
      addToast(e.message || '删除失败', 'error');
    }
  };

  const handleLogout = async () => {
    try {
      await adminLogout();
      addToast('已退出管理员模式', 'success');
      await refreshAuth();
      onNavigateHome();
    } catch (e) {
      addToast('退出失败', 'error');
    }
  };

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div style={{ background: 'rgba(16, 185, 129, 0.15)', width: '36px', height: '36px', borderRadius: 'var(--radius-sm)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#10b981' }}>
            <Shield size={22} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 800 }}>管理员控制台</h2>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>系统状态监控、全局任务审计与存储空间管理</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button className="btn-primary" style={{ padding: '0.55rem 1rem', fontSize: '0.875rem' }} onClick={handleCleanup} disabled={cleaning}>
            <Trash2 size={15} />
            <span>{cleaning ? '正在清理...' : '执行 24h 清理'}</span>
          </button>
          <button className="btn-cancel" style={{ padding: '0.55rem 1rem' }} onClick={handleLogout}>
            <LogOut size={15} />
            <span>退出管理</span>
          </button>
        </div>
      </div>

      {/* Diagnostics Cards */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
          <div style={{ background: 'var(--bg-card)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
              <HardDrive size={16} />
              <span>下载存储占用</span>
            </div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              {stats.disk.storage_dir_formatted}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              磁盘剩余可用: {formatBytes(stats.disk.free_bytes)}
            </div>
          </div>

          <div style={{ background: 'var(--bg-card)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
              <Activity size={16} />
              <span>运行中任务 / 并发</span>
            </div>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#3b82f6' }}>
              {stats.active_downloads}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              系统正常运行: {Math.round(stats.uptime_seconds / 60)} 分钟
            </div>
          </div>

          <div style={{ background: 'var(--bg-card)', padding: '1.25rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
              <Server size={16} />
              <span>核心组件状态</span>
            </div>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <div>yt-dlp: <span style={{ color: stats.yt_dlp_version.includes('未安装') ? '#ef4444' : '#10b981' }}>{stats.yt_dlp_version}</span></div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                ffmpeg: {stats.ffmpeg_available ? <span style={{ color: '#10b981' }}>✓ 就绪</span> : <span style={{ color: '#ef4444' }}>✗ 未就绪</span>}
                &nbsp;|&nbsp;
                MP4Box: {stats.mp4box_version && !stats.mp4box_version.includes('未安装') ? <span style={{ color: '#10b981' }}>✓ 就绪</span> : <span style={{ color: '#f59e0b' }}>未安装</span>}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                Apple Music: {stats.apple_music_available ? <span style={{ color: '#10b981' }}>✓ 配置就绪</span> : <span style={{ color: '#ef4444' }}>✗ 未配置</span>}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Global Task Table */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: '1.25rem', overflowX: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>全系统任务记录 ({tasks.length})</h3>
          <button className="icon-btn" style={{ width: '30px', height: '30px' }} onClick={refreshTasks} title="刷新表格">
            <RefreshCw size={14} />
          </button>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
              <th style={{ padding: '0.6rem 0.75rem' }}>标题 / URL</th>
              <th style={{ padding: '0.6rem 0.75rem' }}>用户标识</th>
              <th style={{ padding: '0.6rem 0.75rem' }}>状态</th>
              <th style={{ padding: '0.6rem 0.75rem' }}>文件大小</th>
              <th style={{ padding: '0.6rem 0.75rem' }}>提交时间</th>
              <th style={{ padding: '0.6rem 0.75rem', textAlign: 'right' }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <td style={{ padding: '0.75rem', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={t.title || t.url}>
                  {t.title || t.url}
                </td>
                <td style={{ padding: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                  {t.user_id === 'admin' ? '👑 Admin' : t.user_id.slice(0, 8)}
                </td>
                <td style={{ padding: '0.75rem' }}>
                  <span className={`status-badge ${t.status}`}>
                    {t.status}
                  </span>
                </td>
                <td style={{ padding: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                  {formatBytes(t.file_size)}
                </td>
                <td style={{ padding: '0.75rem', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                  {new Date(t.created_at).toLocaleTimeString()}
                </td>
                <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                  <button
                    onClick={() => handleDeleteTask(t.id)}
                    style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '0.2rem' }}
                    title="强制删除此任务及文件"
                  >
                    <Trash2 size={15} color="#ef4444" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Real-time System Logs */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', padding: '1.25rem', marginTop: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 700, fontSize: '1.05rem' }}>
            <Server size={18} color="#6366f1" />
            <span>实时运行日志 (data/logs/app.log)</span>
          </div>
          <button className="icon-btn" style={{ width: '30px', height: '30px' }} onClick={loadLogs} title="刷新日志">
            <RefreshCw size={14} />
          </button>
        </div>
        <pre
          ref={logContainerRef}
          style={{
            background: 'var(--bg-primary)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: '1rem',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.8rem',
            color: 'var(--text-secondary)',
            maxHeight: '280px',
            overflowY: 'auto',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
            lineHeight: 1.5,
            scrollBehavior: 'smooth'
          }}
        >
          {logs || '正在获取日志...'}
        </pre>

      </div>
    </div>
  );
}
