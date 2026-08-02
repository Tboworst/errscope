import React from 'react';

// Click-away and Esc handling are owned by the parent (App.jsx).
export default function RowMenu({ items, pos }) {
  const x = Math.max(8, pos.x - 214) + 'px';
  const y = (pos.y + 8) + 'px';

  return (
    <div
      onClick={e => e.stopPropagation()}
      style={{
        position: 'fixed', left: x, top: y, width: 210,
        background: 'var(--panel,#101013)',
        border: '1px solid var(--border2,#27272a)',
        borderRadius: 10, boxShadow: '0 16px 40px rgba(0,0,0,0.55)',
        zIndex: 80, padding: 4,
      }}
    >
      {items.map((mi, i) => (
        <div
          key={i}
          onClick={mi.onClick}
          style={{ padding: '7px 10px', borderRadius: 7, cursor: 'pointer', fontSize: 12.5, color: mi.color }}
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--hover,#18181b)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = ''; }}
        >
          {mi.label}
        </div>
      ))}
    </div>
  );
}
