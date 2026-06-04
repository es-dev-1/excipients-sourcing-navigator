# Excipient Sourcing Navigator

An interactive tool to help pharma and nutra formulators find fitting excipient suppliers, organized by route of administration, functional category, and excipient type.

## Status
Active -- kickoff 2026-05-30

## Goal
Build a web-based tool that allows users to navigate the excipient landscape by route of administration > category > excipient > supplier and quickly identify relevant suppliers for their formulation needs.

## Timeline
- **Start**: 2026-05-30
- **Key milestones**: TBD
- **Deadline**: TBD

## Key contacts
- Elias Schiffbauer (project lead)

## Quick context
The pharma-excipients-landscape project established a comprehensive structure tree mapping excipients to suppliers across five routes of administration (Oral, Injectable, Topical, Ocular, Rectal & Vaginal). This project builds on that foundation to create a practical sourcing tool for PharmaExcipients.com visitors.

## Foundation
The data structure tree lives in `ea-work/data-for-reoccurring-tasks/excipient-sourcing-tree.md` and in `ea-work/projects/pharma-excipients-landscape/excipients.json`.

## Data structure (stage 3 and stage 4)
`excipients.json` is regenerated from `ea-work/data-for-reoccurring-tasks/excipients-landscape-structure.md`, which is the source of truth for the functional categories (stage 3) and the excipients within each category (stage 4). As of 2026-06-04, an excipient can appear under multiple functional categories within the same route of administration when it serves both functions (e.g. Alginic Acid under both Binders and Disintegrants in Oral). Supplier lists (stage 5) are attached per route + excipient and are identical across every category an excipient appears in. To regenerate, rebuild the route > category > excipient tree from the structure markdown and re-attach each excipient's existing supplier list keyed by route + excipient name.

## Open questions
- What technology stack to use?
- How should the tool integrate with the existing PharmaExcipients.com site?
- What filtering or search features beyond the tree navigation?
- Should supplier links point to PharmaExcipients.com supplier pages or external sites?

## Last updated
2026-06-04
