import type { AdminAiCapabilityGroup } from "./adminAiEffectivenessModel";

/**
 * Return capability cards with the same policy language as the legacy runtime.
 */
export function capabilityGroups(): AdminAiCapabilityGroup[] {
  return [
    {
      key: "supported",
      tone: "is-active",
      items: [
        { label: "Permission-aware Quellenabruf", value: "Quellen werden rollen- und berechtigungsbewusst gefiltert." },
        { label: "Fehlerkatalog-Assistenz", value: "Fehlercodes, Ursachen und Lösungen bleiben strukturiert nutzbar." },
        { label: "Konfidenz & Nachvollziehbarkeit", value: "Antworten zeigen Score, Begründung und verwendete Quellen." },
        { label: "Sicherheitsprüfungen", value: "Riskante Wartungshinweise werden vor und nach der Generierung geprüft." }
      ]
    },
    {
      key: "partial",
      tone: "is-stale",
      items: [
        { label: "RAG & Dokumentwissen", value: "Aktiv, aber abhängig von Indexfrische und Quellenqualität." },
        { label: "Golden Quellenabruf Evaluation", value: "Historie ist vorhanden, benötigt regelmäßige Runs für Trends." },
        { label: "OpenAI-Anbindung", value: "Konfiguriert; Fallbacks bleiben möglich." },
        { label: "Wissensnetz", value: "Nur-Lese Analyse verfügbar; keine GraphDB erforderlich." }
      ]
    },
    {
      key: "unsupported",
      tone: "is-muted",
      items: [
        { label: "Autonome Maschinenfreigaben", value: "Die KI darf keine sicherheitskritischen Freigaben erteilen." },
        { label: "Arbeiten unter Spannung", value: "Gefährliche Schritt-für-Schritt-Anleitungen werden entschärft." },
        { label: "Ungefilterte Prompt-/Textabschnitt-Einsicht", value: "Admin-Debug bleibt prompt-sicher und zeigt keine sensiblen Rohtexte." }
      ]
    }
  ];
}
