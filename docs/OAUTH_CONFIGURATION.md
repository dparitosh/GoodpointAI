# OAuth Configuration for PLM Connections

## Overview

GraphTrace supports OAuth 2.0 client credentials flow for authenticating PLM connections through Azure API Gateway and other OAuth-protected REST endpoints. This enables:

- **Passwordless authentication** for service-to-service communication
- **Automatic token refresh** before expiration
- **Token caching** to minimize authentication requests
- **Azure AD integration** for enterprise identity management

## Supported Authentication Methods

### 1. Basic Authentication
Traditional username/password authentication.

```json
{
  "connection_type": "teamcenter",
  "username": "plm_user",
  "password": "secret_password",
  "extra_options": {
    "auth_method": "basic",
    "server_url": "https://plm.example.com/api"
  }
}
```

### 2. Bearer Token (Static)
Pre-configured bearer token (manual refresh required).

```json
{
  "connection_type": "windchill",
  "password": "your-static-bearer-token",
  "extra_options": {
    "auth_method": "bearer",
    "server_url": "https://windchill.example.com/api"
  }
}
```

### 3. OAuth 2.0 (Auto-Refresh) ⭐ NEW
Automatic token management using client credentials flow.

```json
{
  "connection_type": "teamcenter",
  "username": "",
  "password": "",
  "extra_options": {
    "auth_method": "oauth",
    "server_url": "https://apim.azure-api.net/plm/teamcenter",
    "oauth_client_id": "12345678-1234-1234-1234-123456789012",
    "oauth_client_secret": "your-client-secret~value",
    "oauth_token_url": "https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/token",
    "oauth_scope": "api://plm-gateway/.default"
  }
}
```

## Azure API Gateway Configuration

### Step 1: Register Application in Azure AD

1. Go to **Azure Portal** → **Azure Active Directory** → **App registrations**
2. Click **New registration**
3. Configure:
   - **Name**: `GraphTrace PLM Integration`
   - **Supported account types**: Single tenant
   - **Redirect URI**: Leave empty (not needed for client credentials)
4. Click **Register**
5. Note the **Application (client) ID** and **Directory (tenant) ID**

### Step 2: Create Client Secret

1. In your app registration, go to **Certificates & secrets**
2. Click **New client secret**
3. Set description and expiry (max 24 months recommended)
4. Click **Add**
5. **Copy the secret value immediately** (shown only once)

### Step 3: Configure API Permissions

1. Go to **API permissions** → **Add a permission**
2. Choose your API Gateway / backend API
3. Select **Application permissions** (not delegated)
4. Check required scopes (e.g., `API.Read`, `API.Write`)
5. Click **Grant admin consent** for your tenant

### Step 4: Configure Connection in GraphTrace

Using the Admin UI (`http://localhost:5173/#/admin`):

1. Go to **Connections** tab
2. Click **Add Connection**
3. Fill in:
   - **Connection Type**: `teamcenter`, `windchill`, etc.
   - **Name**: `Teamcenter Production`
   - **Extra Options**:
     ```json
     {
       "auth_method": "oauth",
       "server_url": "https://your-apim.azure-api.net/plm/v1",
       "oauth_client_id": "<your-client-id>",
       "oauth_client_secret": "<your-client-secret>",
       "oauth_token_url": "https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token",
       "oauth_scope": "api://<your-api-id>/.default"
     }
     ```
4. Click **Test Connection** to verify
5. Click **Save**

## Token URL Configuration

### Azure AD v2.0 (Recommended)
```
https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/token
```

### Azure AD v1.0
```
https://login.microsoftonline.com/{tenant-id}/oauth2/token
```

### Generic OAuth 2.0 Provider
```
https://your-oauth-provider.com/oauth/token
```

## API Endpoints

### Refresh OAuth Token

Force token refresh for a connection:

```bash
POST /api/admin/connections/{connection_id}/oauth/refresh?force=true
```

**Response:**
```json
{
  "success": true,
  "message": "OAuth token acquired successfully",
  "connection_id": "conn-123",
  "token_preview": "eyJhbGciOiJSUzI1Ni...",
  "cached": false
}
```

### Invalidate Token Cache

Clear cached token for a connection:

```bash
DELETE /api/admin/connections/{connection_id}/oauth/cache
```

### Clear All Token Cache

Clear all cached OAuth tokens (admin):

```bash
POST /api/admin/oauth/clear-cache
```

## Token Lifecycle Management

### Automatic Refresh
- Tokens are cached and automatically refreshed 5 minutes before expiration
- No manual intervention required for production workloads
- Token acquisition is transparent to data source operations

### Manual Refresh
Use the `/oauth/refresh?force=true` endpoint to:
- Test OAuth configuration
- Force re-authentication after credential rotation
- Troubleshoot authentication issues

### Cache Invalidation
Clear token cache when:
- Rotating client secrets
- Changing OAuth scopes
- Troubleshooting authentication failures

## Token Scopes

### Azure API Management
```
"oauth_scope": "api://<application-id>/.default"
```

### Microsoft Graph
```
"oauth_scope": "https://graph.microsoft.com/.default"
```

### Custom Resource
```
"oauth_scope": "api://your-resource-id/access_as_application"
```

### Multiple Scopes
```
"oauth_scope": "api://resource1/.default api://resource2/.default"
```

## Troubleshooting

### Error: "OAuth token acquisition failed"

**Causes:**
1. Invalid client credentials
2. Incorrect token URL
3. Missing API permissions
4. Network connectivity issues

**Solutions:**
1. Verify `oauth_client_id` and `oauth_client_secret` in Azure AD
2. Check token URL format: `https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token`
3. Ensure admin consent is granted for API permissions
4. Test connectivity: `curl -X POST <token_url>`

### Error: "Incomplete OAuth configuration"

Missing required fields. Ensure `extra_options` contains:
- `oauth_client_id`
- `oauth_client_secret`
- `oauth_token_url`

### Token Expires Too Quickly

Azure AD tokens default to 1 hour. To extend:
1. Go to **Azure AD** → **App registrations** → Your app
2. Click **Token configuration**
3. Adjust **Access token lifetime** (max 24 hours)

### Connection Test Fails with HTTP 401/403

**401 Unauthorized:**
- Token expired or invalid
- Clear cache and retry: `DELETE /api/admin/connections/{id}/oauth/cache`

**403 Forbidden:**
- Missing API permissions
- Check Azure AD API permissions and grant admin consent

## Security Best Practices

### 1. Rotate Client Secrets Regularly
- Use Azure Key Vault for secret management
- Rotate secrets every 6-12 months
- Use separate apps for dev/staging/prod

### 2. Use Least Privilege Scopes
- Request only necessary API permissions
- Avoid wildcard scopes (`/*`)
- Review permissions quarterly

### 3. Monitor Token Usage
- Enable Azure AD sign-in logs
- Track token acquisition failures
- Alert on authentication anomalies

### 4. Secure Connection Storage
- Connection credentials are encrypted at rest
- Use `GRAPH_TRACE_CONFIG_ENCRYPTION_KEY` environment variable
- Never log client secrets in plaintext

### 5. Network Security
- Use HTTPS for all OAuth endpoints
- Configure firewall rules for token endpoints
- Enable Azure Private Link for API Management

## Example Configurations

### Teamcenter via Azure APIM
```json
{
  "id": "teamcenter-prod",
  "connection_type": "teamcenter",
  "name": "Teamcenter Production",
  "extra_options": {
    "auth_method": "oauth",
    "server_url": "https://apim.azure.net/plm/teamcenter/v12",
    "oauth_client_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
    "oauth_client_secret": "your-secret~value",
    "oauth_token_url": "https://login.microsoftonline.com/contoso.onmicrosoft.com/oauth2/v2.0/token",
    "oauth_scope": "api://plm-gateway/.default",
    "api_version": "v12",
    "object_types": "Item,ItemRevision"
  }
}
```

### Windchill via Azure APIM
```json
{
  "id": "windchill-staging",
  "connection_type": "windchill",
  "name": "Windchill Staging",
  "extra_options": {
    "auth_method": "oauth",
    "server_url": "https://apim-staging.azure.net/plm/windchill",
    "oauth_client_id": "9876fedc-ba09-8765-4321-fedcba098765",
    "oauth_client_secret": "staging-secret~value",
    "oauth_token_url": "https://login.microsoftonline.com/staging-tenant-id/oauth2/v2.0/token",
    "oauth_scope": "api://windchill-api/.default"
  }
}
```

### 3DEXPERIENCE via Custom OAuth
```json
{
  "id": "3dx-cloud",
  "connection_type": "3dexperience",
  "name": "3DEXPERIENCE Cloud",
  "extra_options": {
    "auth_method": "oauth",
    "server_url": "https://3dexperience.cloud.example.com/api",
    "oauth_client_id": "custom-client-id",
    "oauth_client_secret": "custom-secret",
    "oauth_token_url": "https://oauth.example.com/token",
    "oauth_scope": "plm:read plm:write"
  }
}
```

## Migration from Static Tokens

### Before (Static Bearer Token)
```json
{
  "password": "static-token-12345",
  "extra_options": {
    "auth_method": "bearer",
    "server_url": "https://api.example.com"
  }
}
```

### After (OAuth Auto-Refresh)
```json
{
  "password": "",
  "extra_options": {
    "auth_method": "oauth",
    "server_url": "https://api.example.com",
    "oauth_client_id": "app-id",
    "oauth_client_secret": "secret",
    "oauth_token_url": "https://login.example.com/token"
  }
}
```

## Environment Variable Configuration

For bootstrap/testing, OAuth can be configured via environment variables:

```bash
# .env or system environment
PLM_OAUTH_CLIENT_ID=your-client-id
PLM_OAUTH_CLIENT_SECRET=your-secret
PLM_OAUTH_TOKEN_URL=https://login.microsoftonline.com/tenant/oauth2/v2.0/token
PLM_OAUTH_SCOPE=api://plm/.default
```

Then reference in connection config:
```json
{
  "extra_options": {
    "auth_method": "oauth",
    "oauth_client_id": "${PLM_OAUTH_CLIENT_ID}",
    "oauth_client_secret": "${PLM_OAUTH_CLIENT_SECRET}",
    "oauth_token_url": "${PLM_OAUTH_TOKEN_URL}",
    "oauth_scope": "${PLM_OAUTH_SCOPE}"
  }
}
```

## Related Documentation

- [Admin Configuration Guide](./docs/ADMIN_CONFIG.md)
- [Connection Settings](./docs/USER_GUIDE.md#connection-settings)
- [Azure API Management Setup](./docs/AZURE_APIM_SETUP.md)
- [Security Best Practices](./docs/SECURITY.md)

## Support

For issues or questions:
1. Check backend logs: `python_backend/logs/`
2. Test OAuth manually: `POST /api/admin/connections/{id}/oauth/refresh`
3. Review Azure AD sign-in logs
4. Contact support with connection ID and error message
