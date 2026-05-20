# AI Demo Question Guide

Use these questions for a reliable AI presentation after seeding the demo
database. They are tuned for the realistic demo data from `python seed.py demo`,
not for the artificial golden-test fixtures.

## Setup Check

1. Run `python seed.py demo`.
2. Start the app and log in as `master.admin` with `Demo1234!`.
3. Open the chat from the dashboard or any operations page.
4. Optional: in `/admin/ai`, check that RAG is available and run a stale reindex
   if the knowledge status shows stale or missing chunks.

## Questions

| # | Demo question | Purpose | Expected sources | Good answer signal | Fallback question |
| --- | --- | --- | --- | --- | --- |
| 1 | Welche dringenden Aufgaben sind heute offen? | Show live task retrieval for urgent daily work. | `task` | Mentions urgent/open or in-progress tasks due today, ideally Hydraulikpresse 03 or Spritzgussanlage 04. | Welche urgent Tasks sind heute faellig? |
| 2 | Welche Aufgabe ist an Hydraulikpresse 03 gerade dringend? | Show machine-specific task context. | `task`, `machine` | Connects Hydraulikpresse 03 with the Dichtigkeitspruefung and current urgency. | Welche offenen Tasks gibt es an Hydraulikpresse 03? |
| 3 | Was bedeutet Fehler INS-E-103? | Show exact error-code lookup. | `error` | Explains Druck faellt ab with possible hydraulic causes and a maintenance action. | Was bedeutet Fehler E-103 an Hydraulikpresse 03? |
| 4 | Welche Loesung gibt es fuer Druck faellt ab an Hydraulikpresse 03? | Show solution-oriented error retrieval. | `error`, `machine` | Suggests leak test, valve coil check or filter replacement based on the error catalog. | Welche Loesung gibt es fuer INS-E-103? |
| 5 | Welche Materialien sind bei Hydraulikpresse 03 unter Mindestbestand? | Show inventory retrieval and stock risk. | `inventory` | Names low/zero-stock press materials such as Dichtungssatz Presse or O-Ring-Satz. | Welche Ersatzteile der Hydraulikpresse 03 sind kritisch? |
| 6 | Welche Wartungsaufgaben sind diese Woche faellig? | Show due-date and task planning context. | `task` | Lists due maintenance work in the current week and keeps the answer source-backed. | Welche Tasks sind in den naechsten 7 Tagen faellig? |
| 7 | Welche Maschine hat aktuell offene oder laufende dringende Aufgaben? | Show combined task and machine reasoning. | `task`, `machine` | Names machines with urgent active work, not completed tasks. | Welche Maschinen haben urgent Tasks? |
| 8 | Was ist bei Not-Halt-Kreis offen zu pruefen? | Show safety/error knowledge without inventing steps. | `error` | References the Not-Halt-Kreis catalog entry and mentions door contact, emergency-stop button or safety relay checks. | Was bedeutet INS-E-106? |

## Presentation Notes

- Prefer the exact wording above for the first run; it reduces ambiguity and
  makes source matching easier to explain.
- If the answer has no sources, switch to the fallback question in the same row.
- Avoid non-seeded machine aliases in this demo. The stable seeded machine is
  `Hydraulikpresse 03`.
- For a product demo, highlight the source chips first, then the answer text.
  The key message is that the assistant answers from visible project data.
