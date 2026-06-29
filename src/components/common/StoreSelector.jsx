import { useStoreContext } from '../../context/StoreContext';

export default function StoreSelector() {
  const {
    stores, selectedStoreId, setSelectedStoreId, loading, error,
  } = useStoreContext();

  if (loading) return <span className="store-selector is-muted">店铺加载中</span>;
  if (error) return <span className="store-selector is-error">{error}</span>;
  if (!stores.length) return <span className="store-selector is-muted">暂无店铺数据</span>;

  return (
    <label className="store-selector">
      <span>当前店铺</span>
      <select value={selectedStoreId || ''} onChange={(event) => setSelectedStoreId(event.target.value)}>
        {stores.map((store) => (
          <option key={store.id} value={store.id}>{store.name}</option>
        ))}
      </select>
    </label>
  );
}
