import { isBackendSource } from '../services/dataProvider';
import BackendEmailAccountsPage from './BackendEmailAccountsPage';
import MockEmails from './MockEmails';

export default function Emails() {
  if (isBackendSource) return <BackendEmailAccountsPage />;
  return <MockEmails />;
}
