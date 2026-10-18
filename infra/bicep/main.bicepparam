using './main.bicep'

// MTower Studio — landing-zone deployment settings. See ../../docs/04-azure-landing-zone.md.

param owner = 'me'
param regionCode = 'eus2'
param location = 'eastus2'
param workload = 'mtowerstudio'

// The studio PC's public IP (updated 2026-10-15; home IP drifts). Deploy-Studio.ps1 warns on drift.
param allowedIps = [
  '2.51.71.149'
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
  // ---- Generation models (the studio's own production engine, engine/). Pay-per-use: idle = $0.
  {
    // Compositions with children + Kontext edits (engine image_compose_flux)
    name: 'me-eus2-flux-kontext-pro'
    format: 'Black Forest Labs'
    model: 'FLUX.1-Kontext-pro'
    version: '1'
    sku: 'GlobalStandard'
    capacity: 1
  }
  {
    name: 'me-eus2-flux-2-pro'
    format: 'Black Forest Labs'
    model: 'FLUX.2-pro'
    version: '1'
    sku: 'GlobalStandard'
    capacity: 1
  }
  {
    // Crowd voices (engine voice_gpt_mini_tts)
    name: 'me-eus2-gpt-4o-mini-tts'
    format: 'OpenAI'
    model: 'gpt-4o-mini-tts'
    version: '2025-12-15'
    sku: 'GlobalStandard'
    capacity: 10
  }
  {
    // Acted character voices + narrator (engine voice_gpt_audio)
    name: 'me-eus2-gpt-audio-1-5'
    format: 'OpenAI'
    model: 'gpt-audio-1.5'
    version: '2026-02-23'
    sku: 'GlobalStandard'
    capacity: 10
  }
  // gpt-image-2.5-flare: the subscription limit is 2 in EVERY region and the legacy MTower Foundry holds both
  // (checked 2026-10-18 across 10 regions). Add it here only after MTower's deployment is deleted at cutover.
]

// Second-region media Foundry (me-swc-mtowerstudio-fdy, same RG): East US 2 quota for these is held by the legacy
// MTower Foundry; Sweden Central had free quota (checked 2026-10-18: gpt-image-2 0/2, sora-2 0/9).
param mediaLocation = 'swedencentral'
param mediaRegionCode = 'swc'
param mediaDeployments = [
  {
    // Compositions with prop references + face swap (engine image_compose / face_swap)
    name: 'me-swc-gpt-image-2'
    format: 'OpenAI'
    model: 'gpt-image-2'
    version: '2026-04-21'
    sku: 'GlobalStandard'
    capacity: 2
  }
  {
    name: 'me-swc-sora-2'
    format: 'OpenAI'
    model: 'sora-2'
    version: '2025-12-08'
    sku: 'GlobalStandard'
    capacity: 9
  }
]

// Budget: $700 ceiling (the target tenant's monthly), 70% alert (~$490) per ADR-0002.
param budgetAmount = 700
param budgetEmails = [
  'maelsayed@microsoft.com'
]
param budgetStartDate = '2026-10-01'
