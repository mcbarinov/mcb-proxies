# mcb-proxies

Proxy aggregation and verification service. Collects proxies from multiple sources, continuously checks their availability, and provides an API to get live working proxies.

## Data Sources

A **source** is a group of proxies from a single provider. Each source can provide proxies in two ways:

- `entries_url` — URL to fetch a proxy list from (checked automatically)
- `entries` — manual list of proxy entries

### Entry Formats

Entries can be full or partial:

| Format | Example |
|--------|---------|
| Full URL | `socks5://user:pass@192.168.1.1:1080` |
| Host with port | `192.168.1.1:8080` |
| Host only | `192.168.1.1` |

For partial entries, the source provides default values:
- `default_protocol` — HTTP or SOCKS5
- `default_username` / `default_password`
- `default_port`

Sources are checked automatically (hourly), fetching new proxies from `entries_url`.

## Proxy Verification

All proxies are continuously verified:

1. **Check method** — a request is sent through the proxy to public IP detection services (like httpbin.org/ip, ipify.org, etc.) to verify connectivity and detect the proxy's external IP
2. **Priority** — unchecked proxies first, then oldest checked (>5 min ago)
3. **History** — each proxy keeps last 100 check results
4. **Auto-cleanup** — proxies failing for 1+ hour are automatically deleted

## API

### `GET /api/proxies/live`

Returns working proxies. "Live" means:
- Status is OK
- Last successful check within 15 minutes

#### Parameters

| Parameter | Description |
|-----------|-------------|
| `sources` | Filter by source IDs (comma-separated) |
| `protocol` | `http` or `socks5` |
| `unique_ip` | Return only one proxy per external IP |
| `exclude_gateway` | Exclude proxies where external IP ≠ hostname |
| `format` | `text` (default, one URL per line) or `json` |

#### Examples

```
GET /api/proxies/live
GET /api/proxies/live?protocol=socks5
GET /api/proxies/live?sources=provider1,provider2&unique_ip=true
GET /api/proxies/live?format=json
```

#### Response

**Text format** (default):
```
socks5://user:pass@192.168.1.1:1080
http://192.168.1.2:8080
```

**JSON format**:
```json
{
  "proxies": [
    "socks5://user:pass@192.168.1.1:1080",
    "http://192.168.1.2:8080"
  ]
}
```
