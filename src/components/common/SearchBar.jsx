export default function SearchBar({
  value,
  onChange,
  placeholder = '请输入关键词搜索',
  children,
  onSearch,
  onReset,
}) {
  return (
    <div className="search-panel">
      <label className="search-input">
        <span>⌕</span>
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => event.key === 'Enter' && onSearch()}
          placeholder={placeholder}
        />
      </label>
      {children}
      <button className="button primary" type="button" onClick={onSearch}>查询</button>
      <button className="button ghost" type="button" onClick={onReset}>重置</button>
    </div>
  );
}
