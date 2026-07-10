import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuthContext } from '../context/AuthContext';

function authErrorMessage(error, status) {
  if (error?.errorCode === 'invalid_credentials') return '账号或密码不正确，请重新输入。';
  if (error?.errorCode === 'invalid_mfa_code') return '验证码不正确或已失效，请重新输入。';
  if (error?.errorCode === 'session_expired') return '验证时间已结束，请重新登录。';
  return status === 'mfa_required' ? '暂时无法确认验证码，请稍后重试。' : '暂时无法登录，请稍后重试。';
}

export function AuthPage() {
  const { status, isAuthenticated, login, verifyMfa } = useAuthContext();
  const navigate = useNavigate();
  const location = useLocation();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (status === 'checking') return <AuthShell><p className="auth-loading">正在检查登录状态...</p></AuthShell>;
  if (isAuthenticated) return <Navigate to={location.state?.from || '/workbench'} replace />;
  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      if (status === 'mfa_required') { if (!/^\d{6}$/.test(code)) throw new Error('请输入六位验证码。'); await verifyMfa(code); navigate('/workbench', { replace: true }); }
      else { await login({ loginIdentifier: identifier, password }); setPassword(''); }
    } catch (nextError) { setPassword(''); setCode(''); setError(authErrorMessage(nextError, status)); }
    finally { setBusy(false); }
  };
  return <AuthShell><h1>{status === 'mfa_required' ? '确认身份' : '登录运营中心'}</h1><p>{status === 'mfa_required' ? '请输入六位验证码继续。' : '使用管理员提供的账号和密码登录。'}</p><form onSubmit={submit}>{status === 'mfa_required' ? <input className="auth-code-input" inputMode="numeric" maxLength={6} autoFocus value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))} placeholder="六位验证码" aria-label="六位验证码" /> : <><label>账号<input value={identifier} onChange={(event) => setIdentifier(event.target.value)} autoComplete="username" /></label><label>密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" /></label></>}{error ? <p className="form-error">{error}</p> : null}<button className="button primary auth-submit" disabled={busy}>{busy ? '正在验证...' : status === 'mfa_required' ? '确认登录' : '登录'}</button></form></AuthShell>;
}

export function AuthStatePage({ type }) {
  const { logout } = useAuthContext();
  const text = type === 'forbidden' ? '当前账号没有可操作店铺，请联系管理员' : type === 'expired' ? '登录已过期，请重新登录' : '需要重新验证身份，请重新登录';
  return <AuthShell><h1>{text}</h1><button className="button primary auth-submit" onClick={() => logout()}>重新登录</button></AuthShell>;
}

function AuthShell({ children }) { return <main className="auth-shell"><section className="auth-panel"><div className="auth-brand"><span>ERP</span><strong>多店铺运营中心</strong></div>{children}</section></main>; }
