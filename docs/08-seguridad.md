# 08 — Seguridad

## Autenticación y sesiones
- Password: argon2id; rate limit de login (5/min/IP + backoff por cuenta); 2FA TOTP opcional (obligatorio para plan admin).
- JWT access 15 min (firmado EdDSA, claves rotadas) + refresh 30 días en cookie `httpOnly; Secure; SameSite=Lax`, rotación con detección de reuse (revoca familia).
- CSRF: double-submit token en mutaciones; CORS estricto al dominio propio.

## Tokens CHPP
- `oauth_token` y `secret` cifrados con Fernet (AES128-CBC+HMAC); clave maestra en secret manager/env, rotación soportada (columna `key_version`).
- Nunca se loguean ni viajan al frontend. Solo el worker de sync los descifra en memoria.
- Cumplimiento CHPP: jamás pedimos ni almacenamos contraseña/security code de Hattrick — solo OAuth.
- Revocación en cascada: borrar cuenta → borrar tokens + derecho al olvido (GDPR): purga de datos personales, anonimización de históricos agregados.

## Aplicación
- Validación de entrada 100% Pydantic (API) + zod (frontend forms).
- SQL siempre parametrizado (SQLAlchemy); sin raw SQL con f-strings (regla de lint).
- Headers: HSTS, CSP estricta (nonce para Next), X-Content-Type-Options, Referrer-Policy.
- Rate limiting por capa: Cloudflare (L7 global) → Traefik middleware (por IP) → app (por usuario/endpoint, Redis).
- Secrets: nunca en repo; `.env` solo local; producción vía secret store; escaneo `gitleaks` en CI.
- Dependencias: Dependabot + `pip-audit`/`npm audit` en CI, imágenes base slim escaneadas con Trivy.

## Auditoría y datos
- `audit_log` append-only: login, conexión/revocación CHPP, exports, cambios de plan, accesos admin.
- Logs sin PII (user_id opaco), retención 90 días.
- Backups PostgreSQL cifrados (pgBackRest), restore ensayado trimestralmente; RPO 24 h fase 1 → 1 h con WAL archiving en fase 5.
- Aislamiento multi-tenant: toda query lleva `user_id/team_id` del token — enforced en repositorios (imposible cross-tenant por construcción; test de contrato dedicado).
