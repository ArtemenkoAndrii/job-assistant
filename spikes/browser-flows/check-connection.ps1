<#
  Checks that the Browser MCP endpoint (A-1) is reachable through Cloudflare Access
  with the service token from set-credentials.ps1. Sends an MCP 'initialize' request.
  Works in Windows PowerShell 5.1 and PowerShell 7+.
#>
foreach ($v in 'A1_MCP_URL', 'CF_ACCESS_CLIENT_ID', 'CF_ACCESS_CLIENT_SECRET') {
  if (-not (Get-Item "env:$v" -ErrorAction SilentlyContinue)) {
    Write-Host "Missing $v. Run: . .\set-credentials.ps1" -ForegroundColor Red; exit 1
  }
}
$headers = @{
  'CF-Access-Client-Id'     = $env:CF_ACCESS_CLIENT_ID
  'CF-Access-Client-Secret' = $env:CF_ACCESS_CLIENT_SECRET
  'Accept'                  = 'application/json, text/event-stream'
}
$body = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"spike-check","version":"0.1"}}}'

$status = 0; $text = ''
try {
  $resp = Invoke-WebRequest -Uri $env:A1_MCP_URL -Method Post -Headers $headers -ContentType 'application/json' `
    -Body $body -UseBasicParsing -TimeoutSec 30
  $status = [int]$resp.StatusCode
  $text = [string]$resp.Content
} catch {
  if ($null -eq $_.Exception.Response) {
    Write-Host "Request failed: $($_.Exception.Message)" -ForegroundColor Red; exit 1
  }
  $status = [int]$_.Exception.Response.StatusCode
  $text = [string]$_.ErrorDetails.Message
}

if ($text -match 'serverInfo') {
  Write-Host 'OK: Cloudflare Access accepted the token and the MCP server answered.' -ForegroundColor Green
} elseif ($text -match 'cloudflareaccess|Cloudflare Access|cf-access') {
  Write-Host "HTTP ${status}: Cloudflare Access did not accept the service token (got its login page or error)." -ForegroundColor Red
  Write-Host "Check: Client Id / Secret are correct, and the Access policy of this application uses action 'Service Auth' and includes this token."
} elseif ($status -eq 401 -or $status -eq 403) {
  Write-Host "HTTP ${status} not from Cloudflare Access - most likely Playwright MCP's host check." -ForegroundColor Red
  Write-Host 'Fix on A-1: start Playwright MCP with --allowed-hosts <your-mcp-host>.'
} else {
  Write-Host "HTTP ${status}: unexpected answer. Check that the URL ends with /mcp." -ForegroundColor Yellow
  if ($text) { Write-Host ($text.Substring(0, [Math]::Min(300, $text.Length))) }
}
