import { useEffect } from 'react';

export default function Modal({ open, title, children, onClose, onConfirm, confirmText = '保存', showFooter = true, width }) {
  useEffect(() => {
    const close = (event) => event.key === 'Escape' && onClose();
    if (open) document.addEventListener('keydown', close);
    return () => document.removeEventListener('keydown', close);
  }, [open, onClose]);
  if (!open) return null;
  return <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}><section className="modal-card" role="dialog" aria-modal="true" style={width ? { width } : undefined}><header><h2>{title}</h2><button className="modal-close" onClick={onClose}>×</button></header><div className="modal-body">{children}</div>{showFooter && <footer><button className="button ghost" onClick={onClose}>取消</button><button className="button primary" onClick={onConfirm}>{confirmText}</button></footer>}</section></div>;
}
