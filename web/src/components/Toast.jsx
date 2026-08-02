import React from 'react';

export default function Toast({ message }) {
  if (!message) return null;
  return (
    <div style={{
      position: 'fixed', bottom: 20, right: 20,
      background: 'var(--hover,#18181b)',
      border: '1px solid var(--border2,#27272a)',
      color: 'var(--fg,#fafafa)',
      borderRadius: 10, padding: '12px 16px', fontSize: 13,
      maxWidth: 380, boxShadow: '0 12px 32px rgba(0,0,0,0.5)',
      zIndex: 60, animation: 'toastIn 0.15s ease-out',
    }}>
      {message}
    </div>
  );
}
