import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export default function NewsDigest() {
  const [idx, setIdx] = useState(0);
  const [dir, setDir] = useState(1);
  const [animKey, setAnimKey] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ['news'],
    queryFn: api.getNews,
    staleTime: 5 * 60 * 1000,
  });

  const items = data ?? [];

  if (!isLoading && items.length === 0) return null;

  function goTo(newIdx, direction) {
    if (newIdx === idx) return;
    setDir(direction);
    setAnimKey((k) => k + 1);
    setIdx(newIdx);
  }

  const item = items[idx];

  return (
    <div className="news-digest">
      <div className="news-digest-header">
        <div className="news-digest-label">
          <span className="news-digest-icon">◈</span>
          Daily Digest
        </div>
        {items.length > 0 && (
          <span className="news-digest-counter">{idx + 1} / {items.length}</span>
        )}
      </div>

      {isLoading ? (
        <div className="news-card glass-card news-card-loading">
          <div className="news-skeleton-title" />
          <div className="news-skeleton-body" />
          <div className="news-skeleton-body short" />
        </div>
      ) : (
        <div className="news-card glass-card">
          <div
            key={animKey}
            className={`news-card-content ${dir >= 0 ? 'news-slide-forward' : 'news-slide-back'}`}
          >
            <div className="news-card-title">{item.title}</div>
            <div className="news-card-date">{formatDate(item.scanned_at)}</div>
            <iframe
              className="news-card-body"
              srcDoc={item.body}
              sandbox="allow-same-origin"
              title={item.title}
            />
          </div>

          <div className="news-card-footer">
            <button
              className="news-nav-btn"
              onClick={() => goTo(idx - 1, -1)}
              disabled={idx === 0}
              aria-label="Previous"
            >
              ←
            </button>

            <div className="news-dots">
              {items.slice(0, 12).map((_, i) => (
                <button
                  key={i}
                  className={`news-dot${i === idx ? ' active' : ''}`}
                  onClick={() => goTo(i, i > idx ? 1 : -1)}
                  aria-label={`Go to item ${i + 1}`}
                />
              ))}
              {items.length > 12 && <span className="news-dots-more">…</span>}
            </div>

            <button
              className="news-nav-btn"
              onClick={() => goTo(idx + 1, 1)}
              disabled={idx === items.length - 1}
              aria-label="Next"
            >
              →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
