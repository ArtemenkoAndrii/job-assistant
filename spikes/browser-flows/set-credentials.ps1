<#
  Sets Cloudflare Access credentials for the Browser MCP endpoint (A-1) in the CURRENT terminal only.
  Run it dot-sourced so the variables stay in your session:
      . .\set-credentials.ps1
  Nothing is written to disk or to the PowerShell history.
#>
$url = Read-Host 'A-1 MCP URL (e.g. https://<your-mcp-host>/mcp)'
$id = Read-Host 'CF-Access-Client-Id'
$secretSecure = Read-Host 'CF-Access-Client-Secret' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secretSecure)
try { $secret = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }

$env:A1_MCP_URL = $url.Trim()
$env:CF_ACCESS_CLIENT_ID = $id.Trim()
$env:CF_ACCESS_CLIENT_SECRET = $secret.Trim()
Remove-Variable secret
Write-Host 'Credentials set for this terminal. Next: .\check-connection.ps1'
