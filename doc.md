

Odrs uac remaining devops automation · MD
ODRS / UAC — Remaining DevOps Automation
RBAC is already automated (testing UAC in sandbox). External portals (OHID SSO, OHID Audience Manager) stay manual — not ours.

This is the rest. Verify every item by redeploying Sandbox first.

Easy wins (build now)
1. Private endpoint approval

Now: approve Data Factory access to Cosmos + SQL MI in the portal by hand.
Do: add a pipeline step az network private-endpoint-connection approve.
Verify (sbx): run step, connection shows Approved.
2. DNS + App Gateway routing

Now: map host names to backends by hand (Auth→Identity, AppProvision→Bff, odrs→Bff). DNS records already exist.
Do: put listeners, host names, backend pools, routing rules in the App Gateway Bicep (the conversion you're already doing).
Verify (sbx): agw redeploy + what-if.
Note: blocked behind the prod managed-identity fix (odhappsprd-agw-mi).
3. Health check path

Now: set /HealthCheck on every slot by hand.
Do: set healthCheckPath in appService Bicep.
Verify (sbx): redeploy, APIs show healthy not degraded.
Why it matters: /health vs /HealthCheck made all APIs degraded in prod.
4. ACR auth = Managed Identity

Now: flip to Managed Identity in Deployment Center UI on 3 app services.
Do: set the ACR managed-identity flag in appService Bicep.
Verify (sbx): redeploy.
5. App Insights connection strings (BFF)

Now: paste APPINSIGHTS / APPLICATIONINSIGHTS connection strings by hand.
Do: Bicep refs pulled from the AI instance.
Verify (sbx): redeploy.
6. KV keys + secret shells

Now: hand-create data-protection keys and secret entries.
Do: Bicep creates the keys and empty secret shells. Bicep fills internal values (Cosmos key, AI conn string). External values stay a short manual list.
Verify (sbx): redeploy, keys + shells present.
7. APIM product + subscription

Now: create APIM product, subscription, user and grant 3 APIs by hand.
Do: use apimapi.bicep (already in your shared templates) or az apim.
Verify (sbx): redeploy.
8. Trigger Data Migration ADF job

Now: click "Trigger now" on Odrs-LegacyUsersImport.
Do: az datafactory pipeline create-run in a pipeline step.
Verify (sbx): trigger, run starts.
Bigger build (worth it)
9. SQL script runner

Now: run PreRelease / Release-night / PostMigration scripts by hand, in order.
Do: one reusable SQL-runner stage (same shape as seed-cosmos.ps1), sequenced with stage gates. Re-runs must be idempotent.
Verify (sbx): run, check each script applied.
10. Pipeline orchestration

Now: trigger 17 ODRS pipelines + run the Promote pipeline 3x by hand.
Do: one multi-stage release with dependsOn; collapse Promote into a single run. Keep the approval gate.
Verify (sbx): one release run, green.
11. Smoke checks

Now: log in and eyeball health + seed counts.
Do: a verification stage that curls health URLs and runs the SQL count checks, then asserts pass/fail.
Verify (sbx): smoke run.
Research first
JAMS jobs (import + rebuild-index schedule): check if your JAMS version supports command-line import (jams.exe). If yes, replace the UI import.
UAC client import (ODRS step 5): it's your own app — could add an import API endpoint. Note the ClientSecret can't be re-fetched, only regenerated.
Fix (not new automation — a bug)
UAC Bicep env values: IdentityServer_IssuerUri is invalid and OpenIdConnect_ClientId is partly wrong in identityAppService.json. Right now a KV override hides it. Fix the value at source instead.

