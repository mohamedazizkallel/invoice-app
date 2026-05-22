# Security Checklist

## Pre-Deployment (Critical)

- [ ] Change `SECRET_KEY` in `.env` to a strong random value
- [ ] Set `DEBUG=False` in production `.env`
- [ ] Remove default admin creation from `entrypoint.sh` after first deploy
- [ ] Change default admin password immediately after first login
- [ ] Set strong `POSTGRES_PASSWORD`
- [ ] Enable HTTPS in Dokploy
- [ ] Remove `*migrations/` from `.gitignore`

## Production Hardening

### 1. Environment Variables (.env)
```env
SECRET_KEY=<50+ char random string>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.com
POSTGRES_PASSWORD=<strong password>
```

### 2. Add to settings.py
```python
# File upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880

# Session security
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'

# Password strength
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
```

### 3. Add Rate Limiting
```bash
pip install django-ratelimit
```

### 4. Regular Updates
```bash
pip install --upgrade django
pip list --outdated
```

## Monitoring

- Enable application logging
- Monitor failed login attempts
- Set up error alerting
- Review access logs regularly
- Enable database query logging

## Common Vulnerabilities Mitigated

✅ SQL Injection - Django ORM
✅ XSS - Template auto-escaping
✅ CSRF - Middleware enabled
✅ Clickjacking - X-Frame-Options set
✅ SSL/TLS - Dokploy handles
✅ Secure cookies - When DEBUG=False

## Still Needs Work

⚠️ Rate limiting
⚠️ Input validation beyond Django forms
⚠️ File upload validation
⚠️ 2FA for admins
⚠️ Audit logging
⚠️ Content Security Policy
