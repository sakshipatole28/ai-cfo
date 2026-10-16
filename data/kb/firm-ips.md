---
id: firm-ips
issuer: Firm policy
title: Anand Wealth Partners — Investment Policy Statement (fictional demo firm)
source_url: https://github.com/sakshipatole28/ai-cfo
version: v3
effective: 2026-04-01
kind: Fictional policy used for the demo firm.
---

## Model portfolios
The firm uses four model portfolios. Conservative: 30% equity, 55% debt, 10% gold, 5% cash. Moderate: 50% equity, 35% debt, 10% gold, 5% cash. Moderately aggressive: 70% equity, 20% debt, 5% gold, 5% cash. Aggressive: 80% equity, 12% debt, 5% gold, 3% cash. Each client is mapped to one model after risk profiling.

## Rebalancing bands
A review is triggered when any asset class drifts more than 5 percentage points from the client's model. Drift is measured as the actual share of the portfolio minus the model's target share, and the rupee gap is that difference multiplied by the portfolio value.

## Overlap and concentration thresholds
Two equity funds whose portfolios overlap by 60% or more are flagged for review, and 70% or more is treated as high severity. A single company that makes up 7% or more of the total portfolio after looking through fund holdings is flagged as a concentration.

## Review cadence and approvals
Every client is reviewed at least every 90 days. AI-drafted findings are recommendations to the adviser only; nothing is sent to a client until an adviser with approval rights has reviewed and approved it, and the adviser's rationale is stored with the record of advice.
