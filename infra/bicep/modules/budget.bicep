// MTower Studio — monthly cost budget for the studio resource group (alerts only; it never stops spending).
// Includes the 70% alert requested for the studio (ADR-0002): ~$490 of the $700 ceiling.

param name string
param amount int
param contactEmails array

@description('First day of the budget period, yyyy-MM-01. Fixed: the start date of an existing budget cannot be moved.')
param startDate string

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: name
  properties: {
    category: 'Cost'
    amount: amount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: startDate
    }
    notifications: {
      actual70: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 70 // the requested studio alert (~$490 of $700)
        thresholdType: 'Actual'
        contactEmails: contactEmails
      }
      actual90: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 90
        thresholdType: 'Actual'
        contactEmails: contactEmails
      }
      actual100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: contactEmails
      }
      forecast100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: contactEmails
      }
    }
  }
}

output budgetName string = budget.name
