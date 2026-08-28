import React from 'react';
import { Youtube, Music, ArrowRight } from 'lucide-react';

export default function HomePage({ onSelectService }) {
  return (

    <div>
      <div style={{ textAlign: 'center', margin: '1.5rem 0 2.5rem' }}>
        <h1 style={{ fontSize: '2.25rem', fontWeight: 800, letterSpacing: '-0.025em', marginBottom: '0.75rem' }}>
          选择媒体下载服务
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1.05rem', maxWidth: '520px', margin: '0 auto' }}>
          安全、快速提取媒体流并自动合并封装，支持私有化文件隔离与 24 小时生命周期管理。
        </p>
      </div>

      <div className="service-grid">
        {/* YouTube Card */}
        <div className="service-card youtube-card" onClick={() => onSelectService('youtube')}>
          <div className="service-badge badge-active">已就绪</div>
          <div>
            <div className="service-icon-box yt">
              <Youtube size={32} />
            </div>
            <div className="service-title">YouTube Downloader</div>
            <div className="service-desc">
              基于 yt-dlp 与 ffmpeg，支持原画最高画质音视频自动合并提取，实时进度监控与文件直链。
            </div>
          </div>
          <div className="service-footer">
            <span style={{ color: 'var(--yt-red)' }}>立即使用</span>
            <ArrowRight size={18} color="var(--yt-red)" />
          </div>
        </div>

        {/* Apple Music Card */}
        <div className="service-card apple-card" onClick={() => onSelectService('apple_music')}>
          <div className="service-badge badge-active" style={{ background: 'rgba(250, 35, 59, 0.15)', color: '#fa233b', borderColor: 'rgba(250, 35, 59, 0.3)' }}>已就绪</div>
          <div>
            <div className="service-icon-box am">
              <Music size={32} />
            </div>
            <div className="service-title">Apple Music Downloader</div>
            <div className="service-desc">
              支持单曲与整张专辑原声母带提取，自动写入 iTunes 标签与封面，整张专辑一键打包 ZIP。
            </div>
          </div>
          <div className="service-footer">
            <span style={{ color: 'var(--apple-pink, #fa233b)' }}>立即使用</span>
            <ArrowRight size={18} color="var(--apple-pink, #fa233b)" />
          </div>
        </div>
      </div>
    </div>
  );
}
