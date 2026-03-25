# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it responsibly:

- Email: security@hamsvic.com
- Do NOT open a public issue for security vulnerabilities

## Security Best Practices

1. **Never commit `.env` files** - Use `.env.example` as a template
2. **Use strong passwords** - Minimum 16 characters for admin and database
3. **Generate a unique `DJANGO_SECRET_KEY`** for each deployment
4. **Enable HTTPS** in production (`SECURE_SSL_REDIRECT=True`)
5. **Keep dependencies updated** - Run `pip install --upgrade` regularly
6. **Use cloud storage** (S3/R2) in production for persistent file storage
