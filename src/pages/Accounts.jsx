import { isBackendSource } from '../services/dataProvider';
import BackendAccountsPage from './BackendAccountsPage';
import MockAccounts from './MockAccounts';

export default function Accounts() {
  if (isBackendSource) return <BackendAccountsPage />;
  return <MockAccounts />;
}
