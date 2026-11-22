# Stores your OpenAI API key as a per-user Windows environment variable.
# The key is typed at a hidden prompt, is never shown, and is not written to any project file.
# Remove it later with:  .\set_api_key.ps1 -Remove
param([switch]$Remove)
$ErrorActionPreference = 'Stop'
if ($Remove) {
    [Environment]::SetEnvironmentVariable('OPENAI_API_KEY', $null, 'User')
    Write-Host 'OPENAI_API_KEY removed from your user environment.'
    return
}
$secure = Read-Host 'Paste your OpenAI API key (hidden), then press Enter' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer).Trim()
    if ([string]::IsNullOrWhiteSpace($key)) { throw 'No key entered; nothing was changed.' }
    [Environment]::SetEnvironmentVariable('OPENAI_API_KEY', $key, 'User')
    Write-Host ("Saved. Key length {0} characters; value not displayed." -f $key.Length)
} finally {
    $key = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    $secure.Dispose()
}
