# UI Polish Review

Use this skill when reviewing or making small UI polish recommendations for the Maintenance Assistant App.

## Purpose

Keep UI changes consistent, readable, and operationally useful without redesigning the app.

## Instructions

- Review only the UI surface relevant to the requested change.
- Preserve existing routes, templates, React entry points, CSS architecture, and dark mode behavior.
- Do not introduce a new design system.
- Do not create landing pages, marketing sections, or decorative UI unrelated to maintenance workflows.
- Keep operational pages dense, scannable, and practical for repeated use.
- Prefer clear labels, visible state, compact cards, tables, filters, and action affordances.
- Ensure AI-specific UI shows sources, confidence, uncertainty, fallback state, and no-answer messaging when available.
- Check that text does not overflow buttons, cards, tables, or mobile containers.
- Verify that dark mode remains legible.
- Treat current CSS and frontend changes as user work unless the task requires touching them.

## What To Report

- List UI regressions by severity.
- Mention affected files and selectors/components when known.
- Suggest the smallest safe fix.
- Avoid broad redesign recommendations unless the user explicitly asks for redesign.
