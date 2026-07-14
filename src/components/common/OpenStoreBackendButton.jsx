import { useEffect, useState } from 'react';
import { useAuthContext } from '../../context/AuthContext';
import { useStoreContext } from '../../context/StoreContext';
import dataProvider from '../../services/dataProvider';


const ERROR_MESSAGES = {
  ZINIAO_BROWSER_OPEN_DISABLED: '本机紫鸟入口尚未启用',
  ZINIAO_CLI_NOT_CONFIGURED: '本机尚未配置紫鸟 CLI',
  ZINIAO_CLI_NOT_AVAILABLE: '紫鸟 CLI 当前不可用',
  ZINIAO_PROFILE_NOT_ACTIVE: '请管理员启用紫鸟本机授权配置',
  ZINIAO_PROFILE_UNAVAILABLE: '紫鸟本机授权已失效',
  ZINIAO_STORE_NOT_BOUND: '请管理员先绑定紫鸟店铺',
  ZINIAO_STORE_NOT_FOUND: '紫鸟中未找到该店铺',
  ZINIAO_STORE_MATCH_NOT_UNIQUE: '紫鸟店铺匹配不唯一',
  ZINIAO_STORE_PLATFORM_MISMATCH: '紫鸟店铺平台与系统不一致',
  ZINIAO_STORE_OPEN_IN_PROGRESS: '店铺后台正在打开，请稍候',
  ZINIAO_STORE_OPEN_FAILED: '紫鸟店铺打开失败',
};

function feedbackForError(error) {
  return ERROR_MESSAGES[error?.errorCode] || error?.message || '店铺后台打开失败';
}

export default function OpenStoreBackendButton({ store, compact = false }) {
  const { canAccessStore } = useAuthContext();
  const { isBackendSource } = useStoreContext();
  const [state, setState] = useState({ status: 'idle', message: '' });

  useEffect(() => {
    setState({ status: 'idle', message: '' });
  }, [store?.id]);

  if (!store?.id || !isBackendSource || !canAccessStore(store.id, 'platform.browser.open')) return null;

  const capability = store.browserOpenCapability || {};
  const configured = capability.configured ?? store.browserProfileConfigured;
  const runtimeEnabled = capability.runtimeEnabled !== false;
  const supported = capability.supported !== false;
  const disabledReason = !supported
    ? '首版仅支持 Naver 店铺'
    : !configured
      ? '请管理员先在店铺连接中绑定紫鸟店铺名称'
      : !runtimeEnabled
        ? '本机紫鸟入口尚未启用'
        : '';
  const opening = state.status === 'opening';

  const openStore = async () => {
    if (opening || disabledReason) return;
    setState({ status: 'opening', message: '' });
    try {
      await dataProvider.openStoreBackend(store.id);
      setState({ status: 'success', message: '紫鸟窗口已打开' });
    } catch (error) {
      setState({ status: 'error', message: feedbackForError(error) });
    }
  };

  return (
    <span className={`store-browser-open ${compact ? 'compact' : ''}`}>
      <button
        className={`button ghost ${compact ? 'compact' : ''}`}
        type="button"
        onClick={openStore}
        disabled={opening || Boolean(disabledReason)}
        title={disabledReason || '使用该店铺在紫鸟中绑定的浏览器与 IP 环境打开后台'}
      >
        {opening ? '正在打开...' : '打开店铺后台'}
      </button>
      {state.message ? (
        <span className={`store-browser-open-status ${state.status}`} role="status">{state.message}</span>
      ) : null}
    </span>
  );
}
