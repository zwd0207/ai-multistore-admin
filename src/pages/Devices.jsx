import { isBackendSource } from '../services/dataProvider';
import BackendDeviceEnvironmentPage from './BackendDeviceEnvironmentPage';
import MockDevices from './MockDevices';

export default function Devices() {
  if (isBackendSource) {
    return (
      <BackendDeviceEnvironmentPage
        title="设备管理"
        description="读取并维护当前店铺的设备与环境标签。"
        resourceName="设备环境"
      />
    );
  }

  return <MockDevices />;
}
