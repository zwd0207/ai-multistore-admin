import Modal from './Modal';

export default function DetailModal({ open, title, children, onClose, width = 'min(860px, 92vw)' }) {
  return (
    <Modal open={open} title={title} onClose={onClose} showFooter={false} width={width}>
      <div className="detail-modal">
        <div className="detail-modal-actions">
          <button className="button ghost" onClick={onClose}>关闭</button>
        </div>
        {children}
      </div>
    </Modal>
  );
}
