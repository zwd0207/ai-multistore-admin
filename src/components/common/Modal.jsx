import { useEffect } from 'react';

export default function Modal({
  open,
  title,
  children,
  onClose,
  onConfirm,
  confirmText = '保存',
  confirmDisabled = false,
  showFooter = true,
  width,
}) {
  useEffect(() => {
    const close = (event) => event.key === 'Escape' && onClose();
    if (open) document.addEventListener('keydown', close);
    return () => document.removeEventListener('keydown', close);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="modal-card" role="dialog" aria-modal="true" style={width ? { width } : undefined}>
        <header>
          <h2>{title}</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="关闭">×</button>
        </header>
        <div className="modal-body">{children}</div>
        {showFooter && (
          <footer>
            <button type="button" className="button ghost" onClick={onClose}>取消</button>
            <button type="button" className="button primary" onClick={onConfirm} disabled={confirmDisabled}>{confirmText}</button>
          </footer>
        )}
      </section>
    </div>
  );
}
