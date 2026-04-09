# Real Estate Egypt (`realestate_eg`)

Comprehensive Real Estate & Installment Management for the Egyptian Market — an ERPNext v16 Custom Application.

## Overview

`realestate_eg` is a purpose-built ERPNext v16 custom application covering the entire Egyptian real estate lifecycle:

- **Land Acquisition & NUCA Compliance** — Government land allocation, installment tracking, compliance monitoring
- **Project Structure & Inventory** — Hierarchical project/phase/zone/building/unit management with GIS
- **Costing & Financial Planning** — BOQ, cost allocation, unit profitability analysis
- **Construction Management** — Milestones, progress tracking, escrow account management
- **CRM & Sales** — Lead management, AI-powered matching, multi-scenario quotations, broker management
- **Contract Management** — Digital signature-ready contracts with template engine
- **Installment Management** — 4-15 year payment plans, penalty automation, restructuring, early settlement
- **PDC (Post-Dated Cheque) Management** — Full lifecycle from vault to clearing, OCR scanning, banking integration
- **Cancellation & Refund** — Egyptian law-compliant deductions, refund scheduling, unit transfers
- **Property & Rental Management** — 2025 Rental Law compliance, tenant management, rent collection
- **Facility Management** — Wadeea (maintenance deposit) accounting, maintenance ticketing, utility billing
- **Tax & Compliance** — ETA e-invoicing, e-receipts, foreign buyer compliance, property tax records

## Installation

```bash
bench get-app https://github.com/nsd-eg/realestate_eg.git --branch version-16
bench --site [site-name] install-app realestate_eg
bench --site [site-name] migrate
```

## Requirements

- ERPNext v16
- Frappe Framework v16
- Python 3.12+
- MariaDB 11.x
- Redis

## Target Markets

- **Primary:** Egypt (full localization — NUCA, ETA, CBE, 2025 Rental Law)
- **Secondary:** Saudi Arabia (Phase 2 adaptation)

## License

MIT

## Publisher

Nest Software Development (NSD) — [nsd-eg.com](https://nsd-eg.com)
