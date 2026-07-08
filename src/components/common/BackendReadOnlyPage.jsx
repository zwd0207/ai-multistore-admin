import { useCallback, useEffect, useState } from 'react';
import { useStoreContext } from '../../context/StoreContext';
import DataTable from './DataTable';
import EmptyState from './EmptyState';
import PageHeader from './PageHeader';
import Pagination from './Pagination';
import SearchBar from './SearchBar';

export default function BackendReadOnlyPage({
  title,
  description,
  resourceName,
  loadData,
  columns,
  extraContent,
  emptyState,
}) {
  const { selectedStoreId, loading: storeLoading, error: storeError } = useStoreContext();
  const [query, setQuery] = useState({ keyword: '', page: 1, pageSize: 5 });
  const [draftQuery, setDraftQuery] = useState(query);
  const [result, setResult] = useState({ data: [], total: 0, page: 1, pageSize: 5 });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const load = useCallback(async () => {
    if (storeLoading) return;
    if (storeError) {
      setLoadError(storeError);
      setLoading(false);
      return;
    }
    if (!selectedStoreId) {
      setResult({ data: [], total: 0, page: query.page, pageSize: query.pageSize });
      setLoadError('');
      setLoading(false);
      return;
    }

    setLoading(true);
    setLoadError('');
    try {
      setResult(await loadData({ ...query, storeId: selectedStoreId }));
    } catch (error) {
      setResult({ data: [], total: 0, page: query.page, pageSize: query.pageSize });
      setLoadError(error.message || `${resourceName}数据加载失败`);
    } finally {
      setLoading(false);
    }
  }, [loadData, query, resourceName, selectedStoreId, storeError, storeLoading]);

  useEffect(() => { load(); }, [load]);

  const search = () => setQuery({ ...draftQuery, page: 1 });
  const reset = () => {
    const clean = { keyword: '', page: 1, pageSize: 5 };
    setDraftQuery(clean);
    setQuery(clean);
  };

  return (
    <>
      <PageHeader
        title={title}
        description={description}
        actions={<><button className="button ghost" type="button" onClick={load}>刷新</button><span className="period-chip">暂不支持在线处理</span></>}
      />
      {extraContent}
      <section className="content-card">
        <SearchBar
          value={draftQuery.keyword}
          onChange={(keyword) => setDraftQuery({ ...draftQuery, keyword })}
          onSearch={search}
          onReset={reset}
          placeholder={`搜索${resourceName}`}
        />
        {loadError ? (
          <EmptyState title={`${resourceName}数据加载失败`} description={loadError} />
        ) : !selectedStoreId && !storeLoading ? (
          <EmptyState title="暂无店铺数据" description="请先选择店铺后再查看该页面。" />
        ) : !loading && !(result.data || []).length && emptyState ? (
          <EmptyState title={emptyState.title} description={emptyState.description} actions={emptyState.actions} />
        ) : (
          <>
            <DataTable columns={columns} rows={result.data || []} loading={loading || storeLoading} />
            <Pagination page={query.page} pageSize={query.pageSize} total={result.total} onChange={(page) => setQuery({ ...query, page })} />
          </>
        )}
      </section>
    </>
  );
}
