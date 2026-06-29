import { isBackendSource } from '../services/dataProvider';
import BackendDeviceEnvironmentPage from './BackendDeviceEnvironmentPage';
import MockEnvironment from './MockEnvironment';

export default function Environment() {
  if (isBackendSource) {
    return (
      <BackendDeviceEnvironmentPage
        title="环境管理"
        description="复用 Codex1 device-environments，维护当前店铺登录环境、设备与代理标签。"
        resourceName="环境"
      />
    );
  }

  return <MockEnvironment />;
}
