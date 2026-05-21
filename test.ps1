catch {
    Write-Host " [FAIL] $dbName/$containerName/$docId"
    Write-Host " Error: $_"
    Write-Host " Status code: $($_.Exception.Response.StatusCode.value_)"
    Write-Host " Status Description: $($_.Exception.Response.StatusDescription)"
    
    # Show actual IP being connected to
    Write-Host " DNS Resolution:"
    Resolve-DnsName -Name "$CosmosAccount.documents.azure.com" | 
        Select-Object Name, IPAddress | 
        Format-List | 
        Write-Host

    # Show full exception
    Write-Host " Full Exception: $($_.Exception.GetType().FullName)"
    Write-Host " Inner Exception: $($_.Exception.InnerException.Message)"
    
    # Show response body if any
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader(
            $_.Exception.Response.GetResponseStream())
        Write-Host " Response body: $($reader.ReadToEnd())"
    }
    throw
}
