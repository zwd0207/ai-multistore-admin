import { isBackendSource } from '../services/dataProvider';
import BackendCredentialPage from './BackendCredentialPage';
import MockAccounts from './MockAccounts';

export default function Accounts() {
  if (isBackendSource) return <BackendCredentialPage />;
  return <MockAccounts />;
}
