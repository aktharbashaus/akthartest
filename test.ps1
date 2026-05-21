catch {
    Write-Host " [FAIL] $dbName/$containerName/$docId"
    Write-Host " Error: $_"
    Write-Host " Status code: $($_.Exception.Response.StatusCode.value_)"
    Write-Host " Status Description: $($_.Exception.Response.StatusDescription)"
    
    # Show what IP DNS is resolving to
    Write-Host " DNS Resolution for $CosmosAccount.documents.azure.com :"
    try {
        Resolve-DnsName -Name "$CosmosAccount.documents.azure.com" | 
            ForEach-Object { Write-Host "  -> $($_.Name) : $($_.IPAddress)" }
    } catch {
        Write-Host "  DNS lookup failed"
    }

    # Show inner exception
    Write-Host " Full Exception: $($_.Exception.GetType().FullName)"
    Write-Host " Inner Exception: $($_.Exception.InnerException.Message)"

    # Read the response body for the actual Cosmos error message
    if($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $errorBody = $reader.ReadToEnd()
        Write-Host " Response body: $errorBody"
    }
    throw
}
