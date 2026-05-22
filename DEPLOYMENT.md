# Dokploy Deployment Guide

This guide explains how to deploy the Invoice App Service to Dokploy.

## Prerequisites

- Dokploy instance running and accessible
- Domain name configured (e.g., api.swifttechcorp.com)
- Git repository pushed to GitHub/GitLab

## Files Overview

- `Dockerfile` - Multi-stage build for optimized production image
- `docker-compose.yml` - Orchestrates web app and PostgreSQL database
- `entrypoint.sh` - Handles migrations and starts Gunicorn
- `requirements.txt` - Python dependencies including production packages
- `.env` - Environment variables (DO NOT commit to git)
- `.env.example` - Template for environment variables

## Deployment Steps

### 1. Push Code to Git Repository

```bash
git add .
git commit -m "Dokploy-ready deployment setup"
git push origin main
```

### 2. Create Project in Dokploy

1. Login to your Dokploy dashboard
2. Click "Create New Project"
3. Select "Compose" deployment type
4. Connect your Git repository

### 3. Configure Environment Variables

In Dokploy, add these environment variables:

```env
SECRET_KEY=your-super-secret-key-change-this-in-production
DEBUG=False
ALLOWED_HOSTS=api.swifttechcorp.com,yourdomain.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://api.swifttechcorp.com,https://yourdomain.com

# Database (auto-configured by docker-compose)
POSTGRES_DB=invoice_db
POSTGRES_USER=invoice_user
POSTGRES_PASSWORD=strong-password-here
DB_HOST=db
DB_PORT=5432

# Django
DJANGO_SETTINGS_MODULE=invoice.settings
PYTHONUNBUFFERED=1
```

### 4. Configure Domain

1. In Dokploy, go to your project settings
2. Add your domain (e.g., `api.swifttechcorp.com`)
3. Enable SSL/TLS (Let's Encrypt)
4. Dokploy will automatically configure nginx reverse proxy

### 5. Deploy

1. Click "Deploy" in Dokploy
2. Dokploy will:
   - Pull your code from Git
   - Build the Docker image
   - Start PostgreSQL database
   - Run migrations automatically
   - Collect static files
   - Start Gunicorn server

### 6. Create Superuser (First Time Only)

The entrypoint script creates a default admin user:
- Username: `admin`
- Password: `admin`

**IMPORTANT**: Change this password immediately after first login!

Or SSH into the container and create a custom superuser:

```bash
docker exec -it <container_name> python manage.py createsuperuser
```

## Architecture

```
┌─────────────────────────────────────────────┐
│          Dokploy (nginx reverse proxy)       │
│          SSL/TLS + Domain Routing           │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│         Web Container (Python/Django)        │
│         - Gunicorn WSGI Server              │
│         - 3 workers, 120s timeout            │
│         - Port 8000                          │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│         Database Container (PostgreSQL)      │
│         - PostgreSQL 16                      │
│         - Persistent volume                  │
└─────────────────────────────────────────────┘
```

## Volumes

The setup creates persistent volumes for:

- `invoice_postgres_data` - Database data
- `invoice_media_data` - Uploaded files (logos, invoices)
- `invoice_static_data` - Static files (CSS, JS, images)

These volumes persist even if containers are recreated.

## Troubleshooting

### Check Logs

```bash
# View web container logs
docker logs <web_container_name>

# View database logs
docker logs <db_container_name>

# Follow logs in real-time
docker logs -f <container_name>
```

### Access Container Shell

```bash
docker exec -it <web_container_name> bash
```

### Run Management Commands

```bash
# Inside container
python manage.py migrate
python manage.py collectstatic
python manage.py createsuperuser
```

### Database Connection Issues

If migrations fail, check:
1. Database container is healthy: `docker ps`
2. Environment variables are set correctly
3. Database credentials match in .env

### Static Files Not Loading

Run collectstatic manually:
```bash
docker exec -it <web_container_name> python manage.py collectstatic --noinput
```

## Production Checklist

- [ ] Change `SECRET_KEY` to a strong random value
- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS` with your domain
- [ ] Add domain to `DJANGO_CSRF_TRUSTED_ORIGINS`
- [ ] Use strong `POSTGRES_PASSWORD`
- [ ] Enable SSL/TLS in Dokploy
- [ ] Change default admin password
- [ ] Set up database backups
- [ ] Configure monitoring/alerts

## Maintenance

### Update Application

```bash
git push origin main  # Dokploy auto-deploys on push
```

Or manually trigger deployment in Dokploy dashboard.

### Database Backup

```bash
docker exec <db_container_name> pg_dump -U invoice_user invoice_db > backup.sql
```

### Database Restore

```bash
docker exec -i <db_container_name> psql -U invoice_user invoice_db < backup.sql
```

## Support

For issues with:
- Dokploy: https://docs.dokploy.com
- Django: https://docs.djangoproject.com
- PostgreSQL: https://www.postgresql.org/docs/
