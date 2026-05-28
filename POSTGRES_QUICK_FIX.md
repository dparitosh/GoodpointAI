# Quick Reference: PostgreSQL Port Configuration Fix

## For Your Customer: PostgreSQL Connection Failing?

**The Issue:**
```
Error: could not connect to server: Connection refused
Is the server running on host "XXX" and accepting TCP/IP connections on port 5433?
```

**The Problem:**
Your PostgreSQL is running on the standard port **5432**, but the application is configured to connect to port **5433**.

---

## ✓ The Fix (Choose One)

### Option 1: Set Environment Variables (RECOMMENDED)

When starting the application, set these environment variables:

**Windows (PowerShell):**
```powershell
$env:POSTGRES_HOST = "YOUR_POSTGRES_HOST"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_USER = "postgres"
$env:POSTGRES_PASSWORD = "YOUR_PASSWORD"
$env:POSTGRES_DATABASE = "graphtrace"

# Then start the application
python -m uvicorn main:app --host 0.0.0.0 --port 8011
```

**Linux/Mac (Bash):**
```bash
export POSTGRES_HOST=YOUR_POSTGRES_HOST
export POSTGRES_PORT=5432
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=YOUR_PASSWORD
export POSTGRES_DATABASE=graphtrace

python -m uvicorn main:app --host 0.0.0.0 --port 8011
```

**Docker Compose:**
```yaml
services:
  api:
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: your_password
      POSTGRES_DATABASE: graphtrace
```

**Kubernetes:**
```yaml
env:
  - name: POSTGRES_HOST
    value: "postgres-service"
  - name: POSTGRES_PORT
    value: "5432"
  - name: POSTGRES_USER
    value: "postgres"
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: postgres-credentials
        key: password
  - name: POSTGRES_DATABASE
    value: "graphtrace"
```

### Option 2: Update CONNECTION STRING (If using DATABASE_URL)

Edit `.env` or set the environment variable:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@YOUR_HOST:5432/graphtrace
```

**Note:** Option 1 is better for flexibility and security.

---

## ✓ Quick Test

Once configured, test the connection:

**Using Python:**
```bash
python scripts/test_postgres_connection.py
```

**Using curl (after app starts):**
```bash
curl http://localhost:8011/health
```

Expected response:
```json
{
  "status": "ok",
  "dependencies": {
    "postgres": {
      "ok": true
    }
  }
}
```

---

## ✓ Reference Values

| Variable | Value | Required |
|----------|-------|----------|
| `POSTGRES_HOST` | Your PostgreSQL hostname or IP | Yes |
| `POSTGRES_PORT` | `5432` (standard) or your custom port | No (defaults to 5432) |
| `POSTGRES_USER` | Usually `postgres` | No (defaults to postgres) |
| `POSTGRES_PASSWORD` | Your database password | Yes |
| `POSTGRES_DATABASE` | `graphtrace` | No (defaults to graphtrace) |

---

## ✓ If It Still Fails

1. **Verify PostgreSQL is running:**
   ```bash
   netstat -tuln | grep 5432
   # or
   psql -h YOUR_HOST -p 5432 -U postgres -c "SELECT version();"
   ```

2. **Test basic connectivity:**
   ```bash
   python << 'EOF'
   import psycopg
   conn = psycopg.connect(
       host="YOUR_HOST",
       port=5432,
       user="postgres",
       password="YOUR_PASSWORD",
       dbname="graphtrace"
   )
   print("✓ Connected!")
   conn.close()
   EOF
   ```

3. **Check firewall:**
   - Ensure port 5432 is not blocked
   - Verify network connectivity to PostgreSQL host

4. **For detailed troubleshooting:**
   - See `POSTGRESQL_CONNECTION_TROUBLESHOOTING.md`
   - Run the diagnostic script: `python scripts/test_postgres_connection.py`

---

## ✓ Why This Changed?

**Development Environment:**
- Uses port **5433** (custom) to avoid conflicts with local PostgreSQL
- `DATABASE_URL` hardcoded in `.env` files

**Customer/Production Environment:**
- Uses port **5432** (standard PostgreSQL port)
- Should use `POSTGRES_*` environment variables for flexibility
- Allows same app to work on any port or host

---

## ✓ Key Points

✓ Default port is 5432 (standard PostgreSQL)  
✓ `POSTGRES_*` variables are more flexible than `DATABASE_URL`  
✓ You can use custom ports if needed  
✓ Password is required  
✓ Run diagnostic script if unsure: `python scripts/test_postgres_connection.py`  

---

## ✓ Need Help?

**Questions about:**
- **Connection strings** → See `POSTGRESQL_CONNECTION_TROUBLESHOOTING.md`
- **Docker/Kubernetes** → See `POSTGRESQL_CONNECTION_TROUBLESHOOTING.md` sections for those
- **Port forwarding/SSH tunnels** → See "Common Errors" section
- **Cloud providers** → See "Production" section in full guide

---

**Latest Commit:** 0d35af3 - Add PostgreSQL connection troubleshooting guide  
**Updated:** May 28, 2026
