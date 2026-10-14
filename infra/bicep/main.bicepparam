using './main.bicep'

// MTower Studio — landing-zone deployment settings. See ../../docs/04-azure-landing-zone.md.

param owner = 'me'
param regionCode = 'eus2'
param location = 'eastus2'
param workload = 'mtowerstudio'

// The studio PC's public IP (detected 2026-10-14). Deploy-Studio.ps1 re-detects and overrides on each run.
param allowedIps = [
  '86.97.91.184'
]

// Existing Log Analytics workspace (same sub). Empty = no diagnostics.
param logAnalyticsWorkspaceId = '/subscriptions/ac25e0cf-ad43-46d5-8a70-017cf4f275be/resourceGroups/me-eus-mgmt/providers/Microsoft.OperationalInsights/workspaces/me-eus-mgmt-central'

// Wave 1 fleet: cheap reasoning (agents) + flagship vision (Image QA / Continuity).
// Image / video / speech models are added in Waves 2-3. Pay-per-use (Global Standard): idle deployments cost nothing.
param modelDeployments = [
  {
    // Reasoning for Orchestrator, Script, Director, Research, Studio Critic, Stunt/Action
    name: 'me-eus2-gpt-5-6-terra'
    format: 'OpenAI'
    model: 'gpt-5.6-terra'
    version: '2026-07-09'
    sku: 'GlobalStandard'
    capacity: 100
  }
  {
    // Vision QA reviewer (Image QA) + Continuity (cross-frame)
    name: 'me-eus2-gpt-5-6-sol'
    format: 'OpenAI'
    model: 'gpt-5.6-sol'
    version: '2026-07-09'
    sku: 'GlobalStandard'
    capacity: 100
  }
]

// Budget: $700 ceiling (the target tenant's monthly), 70% alert (~$490) per ADR-0002.
param budgetAmount = 700
param budgetEmails = [
  'maelsayed@microsoft.com'
]
param budgetStartDate = '2026-10-01'
