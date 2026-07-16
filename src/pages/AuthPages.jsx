import { useEffect, useRef, useState } from 'react';
import {
  Link, Navigate, useLocation, useNavigate, useSearchParams,
} from 'react-router-dom';
import { useAuthContext } from '../context/AuthContext';
import backendApi from '../services/backendApi';

const RECOVERY_CODE_PATTERN = /^[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}$/;

function authErrorMessage(error, status) {
  if (error?.errorCode === 'invalid_credentials') return '账号或密码不正确，请重新输入。';
  if (['invalid_mfa_code', 'mfa_invalid'].includes(error?.errorCode)) return '验证码或恢复码不正确，请重新输入。';
  if (error?.errorCode === 'session_expired') return '验证时间已结束，请重新登录。';
  return status === 'mfa_required' ? '暂时无法确认验证码，请稍后重试。' : '暂时无法登录，请稍后重试。';
}

function passwordValidation(password, confirmation) {
  if (password.length < 12) return '密码至少需要 12 个字符。';
  if (!/[a-z]/.test(password) || !/[A-Z]/.test(password) || !/\d/.test(password)) {
    return '密码需要同时包含大写字母、小写字母和数字。';
  }
  if (password !== confirmation) return '两次输入的密码不一致。';
  return '';
}

export function AuthPage() {
  const {
    status, isAuthenticated, login, verifyMfa, logout,
  } = useAuthContext();
  const navigate = useNavigate();
  const location = useLocation();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [localMfaCode, setLocalMfaCode] = useState('');
  const [secondsRemaining, setSecondsRemaining] = useState(null);
  const [localCodeUnavailable, setLocalCodeUnavailable] = useState(false);
  const secondsRef = useRef(null);
  const localCodeRequestRef = useRef(false);

  useEffect(() => {
    if (status !== 'mfa_required') return undefined;
    let active = true;
    const fetchLocalMfaCode = async () => {
      if (!active || localCodeRequestRef.current) return;
      localCodeRequestRef.current = true;
      try {
        const result = await backendApi.getLocalMfaCode();
        if (!active) return;
        const nextCode = typeof result?.code === 'string' ? result.code : String(result?.code || '');
        const nextSeconds = Math.max(0, Number(result?.seconds_remaining) || 0);
        setLocalMfaCode(/^\d{6}$/.test(nextCode) ? nextCode : '');
        setLocalCodeUnavailable(!/^\d{6}$/.test(nextCode));
        secondsRef.current = nextSeconds;
        setSecondsRemaining(nextSeconds);
      } catch {
        if (active) {
          setLocalMfaCode('');
          secondsRef.current = null;
          setSecondsRemaining(null);
          setLocalCodeUnavailable(true);
        }
      } finally {
        localCodeRequestRef.current = false;
      }
    };
    fetchLocalMfaCode();
    const timer = window.setInterval(() => {
      if (secondsRef.current === null) return;
      if (secondsRef.current <= 1) {
        secondsRef.current = 0;
        setLocalMfaCode('');
        setSecondsRemaining(0);
        fetchLocalMfaCode();
        return;
      }
      secondsRef.current -= 1;
      setSecondsRemaining(secondsRef.current);
    }, 1000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [status]);

  if (status === 'checking') return <AuthShell><p className="auth-loading">正在检查登录状态...</p></AuthShell>;
  if (isAuthenticated) return <Navigate to={location.state?.from || '/workbench'} replace />;

  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      if (status === 'mfa_required') {
        const normalizedCode = code.trim().toUpperCase();
        if (!/^\d{6}$/.test(normalizedCode) && !RECOVERY_CODE_PATTERN.test(normalizedCode)) {
          throw new Error('请输入六位验证码或有效恢复码。');
        }
        await verifyMfa(normalizedCode);
        navigate('/workbench', { replace: true });
      } else {
        await login({ loginIdentifier: identifier, password });
        setPassword('');
      }
    } catch (nextError) {
      setPassword('');
      setCode('');
      setError(nextError.message?.startsWith('请输入') ? nextError.message : authErrorMessage(nextError, status));
    } finally {
      setBusy(false);
    }
  };

  const isMfa = status === 'mfa_required';
  return (
    <AuthShell>
      <h1>{isMfa ? '确认身份' : '登录运营中心'}</h1>
      <p>{isMfa ? '请输入身份验证器中的六位验证码，也可以使用一次性恢复码。' : '使用管理员提供的账号和密码登录。'}</p>
      <form onSubmit={submit}>
        {isMfa ? (
          <>
            <div className="mfa-local-code" aria-label="本地测试验证码">
              {Array.from({ length: 6 }, (_, index) => <span className="mfa-code-digit" key={index}>{localMfaCode[index] || ''}</span>)}
            </div>
            {localMfaCode ? (
              <div className="mfa-local-code-meta">
                <span>本地测试验证码</span><span>{secondsRemaining} 秒后更新</span>
                <button className="button ghost mfa-fill-button" type="button" onClick={() => setCode(localMfaCode)}>填入验证码</button>
              </div>
            ) : null}
            {localCodeUnavailable ? (
              <div className="mfa-code-unavailable">
                <span>请输入身份验证器生成的验证码。</span>
                <button className="button ghost" type="button" onClick={() => logout().catch(() => {})}>返回账号登录</button>
              </div>
            ) : null}
            <input
              className="auth-code-input"
              maxLength={14}
              autoFocus
              value={code}
              onChange={(event) => setCode(event.target.value.toUpperCase().replace(/[^A-F0-9-]/g, ''))}
              placeholder="验证码或恢复码"
              aria-label="验证码或恢复码"
              autoComplete="one-time-code"
            />
          </>
        ) : (
          <>
            <label>账号<input value={identifier} onChange={(event) => setIdentifier(event.target.value)} autoComplete="username" /></label>
            <label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" /></label>
          </>
        )}
        {error ? <p className="form-error">{error}</p> : null}
        <button className="button primary auth-submit" disabled={busy}>{busy ? '正在验证...' : isMfa ? '确认登录' : '登录'}</button>
      </form>
      {!isMfa ? <div className="auth-links"><Link to="/forgot-password">忘记密码</Link></div> : null}
    </AuthShell>
  );
}

export function AcceptInvitationPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [enrollment, setEnrollment] = useState(null);
  const [qrCode, setQrCode] = useState('');
  const [code, setCode] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    if (!enrollment?.otpauth_uri) return undefined;
    import('qrcode')
      .then(({ default: QRCode }) => QRCode.toDataURL(
        enrollment.otpauth_uri,
        { width: 224, margin: 1, errorCorrectionLevel: 'M' },
      ))
      .then((value) => { if (active) setQrCode(value); })
      .catch(() => { if (active) setQrCode(''); });
    return () => { active = false; };
  }, [enrollment]);

  const acceptInvitation = async (event) => {
    event.preventDefault();
    const validationError = passwordValidation(password, confirmation);
    if (!token) return setError('邀请链接缺少验证信息，请联系管理员重新发送。');
    if (validationError) return setError(validationError);
    setBusy(true);
    setError('');
    try {
      const result = await backendApi.acceptTenantInvitation({ token, password });
      setEnrollment(result);
      setPassword('');
      setConfirmation('');
    } catch (requestError) {
      setError(requestError.errorCode === 'invitation_expired' ? '邀请已过期，请联系管理员重新发送。' : '邀请无法使用，请联系管理员确认。');
    } finally {
      setBusy(false);
    }
    return undefined;
  };

  const completeEnrollment = async (event) => {
    event.preventDefault();
    if (!/^\d{6}$/.test(code)) return setError('请输入身份验证器中的六位验证码。');
    setBusy(true);
    setError('');
    try {
      const result = await backendApi.completeMfaEnrollment({
        enrollment_token: enrollment.enrollment_token,
        code,
      });
      setRecoveryCodes(Array.isArray(result?.recovery_codes) ? result.recovery_codes : []);
      setEnrollment(null);
      setQrCode('');
      setCode('');
    } catch {
      setError('验证码不正确或绑定已超时，请重新扫码后再试。');
    } finally {
      setBusy(false);
    }
    return undefined;
  };

  if (recoveryCodes.length) {
    return (
      <AuthShell>
        <h1>账号已启用</h1>
        <p>恢复码每个只能使用一次。请妥善保管，离开此页后系统不会再次展示。</p>
        <div className="recovery-code-grid">{recoveryCodes.map((item) => <code key={item}>{item}</code>)}</div>
        <button className="button primary auth-submit" type="button" onClick={() => navigate('/', { replace: true })}>前往登录</button>
      </AuthShell>
    );
  }

  if (enrollment) {
    return (
      <AuthShell>
        <h1>绑定身份验证器</h1>
        <p>使用手机身份验证器扫描二维码，再输入当前六位验证码。</p>
        {qrCode ? <img className="mfa-qr-code" src={qrCode} alt="身份验证器绑定二维码" /> : <div className="mfa-qr-placeholder">二维码生成中...</div>}
        <details className="mfa-secret-fallback"><summary>无法扫码</summary><code>{enrollment.mfa_secret}</code></details>
        <form onSubmit={completeEnrollment}>
          <label>六位验证码<input className="auth-code-input" inputMode="numeric" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))} autoComplete="one-time-code" /></label>
          {error ? <p className="form-error">{error}</p> : null}
          <button className="button primary auth-submit" disabled={busy}>{busy ? '正在确认...' : '完成绑定'}</button>
        </form>
      </AuthShell>
    );
  }

  return (
    <AuthShell>
      <h1>接受运营账号邀请</h1>
      <p>设置登录密码后，需要绑定手机身份验证器。</p>
      <form onSubmit={acceptInvitation}>
        <label>设置密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" /></label>
        <label>再次输入密码<input type="password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="new-password" /></label>
        {error ? <p className="form-error">{error}</p> : null}
        <button className="button primary auth-submit" disabled={busy}>{busy ? '正在创建账号...' : '继续绑定身份验证器'}</button>
      </form>
    </AuthShell>
  );
}

export function PasswordResetPage({ requestOnly = false }) {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event) => {
    event.preventDefault();
    if (!requestOnly) {
      const validationError = passwordValidation(password, confirmation);
      if (!token) return setError('重置链接缺少验证信息，请重新申请。');
      if (validationError) return setError(validationError);
    }
    setBusy(true);
    setError('');
    try {
      if (requestOnly) await backendApi.requestPasswordReset({ email });
      else await backendApi.completePasswordReset({ token, password });
      setCompleted(true);
    } catch {
      setError(requestOnly ? '暂时无法提交申请，请稍后重试。' : '重置链接无效或已过期，请重新申请。');
    } finally {
      setBusy(false);
    }
    return undefined;
  };

  return (
    <AuthShell>
      <h1>{requestOnly ? '找回密码' : '设置新密码'}</h1>
      <p>{completed ? (requestOnly ? '如果账号存在，重置邮件将发送到该邮箱。' : '密码已更新，所有旧登录会话已退出。') : (requestOnly ? '输入注册邮箱以接收密码重置链接。' : '新密码至少 12 个字符，并包含大小写字母和数字。')}</p>
      {!completed ? (
        <form onSubmit={submit}>
          {requestOnly ? <label>注册邮箱<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required /></label> : (
            <>
              <label>新密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" /></label>
              <label>再次输入密码<input type="password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="new-password" /></label>
            </>
          )}
          {error ? <p className="form-error">{error}</p> : null}
          <button className="button primary auth-submit" disabled={busy}>{busy ? '正在提交...' : requestOnly ? '发送重置邮件' : '更新密码'}</button>
        </form>
      ) : null}
      <div className="auth-links"><Link to="/">返回登录</Link></div>
    </AuthShell>
  );
}

export function AuthStatePage({ type }) {
  const { logout } = useAuthContext();
  if (type === 'unavailable') return <AuthShell><h1>系统暂时无法登录</h1></AuthShell>;
  const text = type === 'forbidden' ? '当前账号没有可访问的数据，请联系管理员' : type === 'expired' ? '登录已过期，请重新登录' : '需要重新验证身份，请重新登录';
  return <AuthShell><h1>{text}</h1><button className="button primary auth-submit" onClick={() => logout()}>重新登录</button></AuthShell>;
}

function AuthShell({ children }) {
  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="auth-brand"><span>ERP</span><strong>多店铺运营中心</strong></div>
        {children}
      </section>
    </main>
  );
}
