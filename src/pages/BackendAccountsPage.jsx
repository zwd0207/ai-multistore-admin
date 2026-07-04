import PageHeader from '../components/common/PageHeader';
import StoreMembershipReadonlyPanel from '../components/common/StoreMembershipReadonlyPanel';
import UserInvitationReadonlyPanel from '../components/common/UserInvitationReadonlyPanel';
import BackendCredentialPage from './BackendCredentialPage';
import BackendPlatformLoginSection from './BackendPlatformLoginSection';

export default function BackendAccountsPage() {
  return (
    <>
      <PageHeader
        title="账号管理"
        description="区分人工平台后台登录信息与后续 API 调用凭证，当前均只保存本地配置。"
        actions={<span className="period-chip">本地后端写入</span>}
      />
      <StoreMembershipReadonlyPanel />
      <UserInvitationReadonlyPanel />
      <BackendPlatformLoginSection />
      <BackendCredentialPage embedded />
    </>
  );
}
