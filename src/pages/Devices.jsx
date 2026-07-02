import { isBackendSource } from '../services/dataProvider';
import BackendDeviceEnvironmentPage from './BackendDeviceEnvironmentPage';
import MockDevices from './MockDevices';

export default function Devices() {
  if (isBackendSource) {
    return (
      <BackendDeviceEnvironmentPage
        title="设备与账号"
        description="查看当前店铺的设备环境、登录状态和账号风险提醒。"
        resourceName="设备环境"
      />
    );
  }

  return <MockDevices />;
}
