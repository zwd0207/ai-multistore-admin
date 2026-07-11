# Local PXG Naver Trial

Run `powershell -ExecutionPolicy Bypass -File scripts/start-local-pxg-naver-trial.ps1` from the repository root. The command creates or reuses `backend/.local-trial/pxg-naver-artificial-trial.sqlite3`, writes the one-time local operator handoff to `backend/.local-trial/operator-credentials.txt`, and prints only the local frontend URL.

Stop the isolated processes with `powershell -ExecutionPolicy Bypass -File scripts/stop-local-pxg-naver-trial.ps1`. Reset only the local rehearsal state with `python scripts/provision_local_pxg_naver_trial.py --reset` from `codex1/backend`.

Double-click `查看PXG试运营验证码.cmd` in the repository root to see the current six-digit MFA code. The display refreshes automatically and never prints the underlying MFA secret.
