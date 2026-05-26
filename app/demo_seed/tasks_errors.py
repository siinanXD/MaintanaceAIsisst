"""Static demo seed definitions."""

TASK_DEFINITIONS = [
    # (
    #     titel, beschreibung, priorität, status, fälligkeit_tage,
    #     abteilung, maschine_name, worker_username
    # )
    # Instandhaltung
    (
        "Hydraulikpresse 03 – Dichtigkeitsprüfung",
        "Sämtliche Hydraulikverbindungen und Zylinderanschlüsse auf Leckagen prüfen. "
        "Druckverlustmessung durchführen, Ergebnis in der Wartungsakte dokumentieren.",
        "urgent",
        "in_progress",
        0,
        "Instandhaltung",
        "Hydraulikpresse 03",
        "thomas.hoffmann",
    ),
    (
        "CNC-Fräse 01 – Spindellager tauschen",
        "Austausch des Hauptspindellagers nach 8.200 Betriebsstunden. "
        "Lager-Kit liegt in Lager vor, Ausfallzeit ca. 4 h einplanen.",
        "urgent",
        "open",
        1,
        "Instandhaltung",
        "CNC-Fräse 01",
        None,
    ),
    (
        "Kompressorstation 07 – Ölwechsel und Filterwechsel",
        "Jährlicher Ölwechsel inkl. Öl- und Luftfilter. "
        "Betriebsstundenzähler notieren, Kondensatableiter prüfen.",
        "soon",
        "open",
        3,
        "Instandhaltung",
        "Kompressorstation 07",
        None,
    ),
    (
        "Roboterzelle 09 – TCP-Kalibrierung nach Crash",
        "Nach Kollision mit Bauteil: Werkzeugmittelpunkt neu einmessen, "
        "alle Achsen auf mechanischen Schaden prüfen, Protokoll an Qualität.",
        "urgent",
        "done",
        -2,
        "Instandhaltung",
        "Roboterzelle 09",
        "markus.wagner",
    ),
    (
        "Förderband Linie A – Gurtspannung prüfen",
        "Gurt visuell auf Risse und Verschleiß kontrollieren. "
        "Spannung mit Richtwert 200 N/m² vergleichen, ggf. nachspannen.",
        "soon",
        "in_progress",
        1,
        "Instandhaltung",
        "Förderband Linie A",
        "sandra.becker",
    ),
    (
        "Spritzgussanlage 04 – Heizkabel Heizzone 3 wechseln",
        "Heizzone 3 zeigt Ausfall bei 230 V Prüfung. "
        "Kabel-Set auf Lager, Tausch im Stillstand Spätschicht.",
        "urgent",
        "open",
        0,
        "Instandhaltung",
        "Spritzgussanlage 04",
        None,
    ),
    (
        "Montagelinie 05 – Not-Halt-Kreis testen",
        "Jährliche Sicherheitsprüfung aller Not-Halt-Taster und Türkontakte. "
        "Schaltplan Rev. 4 verwenden, Nachweis für BG-Prüfung erstellen.",
        "normal",
        "open",
        7,
        "Instandhaltung",
        "Montagelinie 05",
        None,
    ),
    (
        "Prüfstand 08 – Kontaktleisten reinigen und prüfen",
        "Oxidierte Kontakte auf Prüfadapter Nr. 3 und 7 gereinigt. "
        "Übergangswiderstand < 10 mΩ dokumentieren.",
        "normal",
        "done",
        -5,
        "Instandhaltung",
        "Prüfstand 08",
        "kevin.schulze",
    ),
    (
        "Waschanlage 11 – Filtereinsatz tauschen",
        "Filtereinsatz nach 250 Betriebsstunden (Vorgabe Hersteller Henkel) wechseln. "
        "Konzentration im Waschbad nachmessen und ggf. korrigieren.",
        "normal",
        "open",
        4,
        "Instandhaltung",
        "Waschanlage 11",
        None,
    ),
    (
        "Laserbeschrifter 10 – Absaugung reinigen",
        "Absaugkanal und Schutzglas visuell prüfen. "
        "Schutzglas gereinigt oder getauscht, Laserleistung nachmessen.",
        "soon",
        "in_progress",
        2,
        "Instandhaltung",
        "Laserbeschrifter 10",
        "miriam.krause",
    ),
    # Produktion
    (
        "CNC-Fräse 01 – Erstmuster Auftrag 4912 freigeben",
        "Erstmusterprüfbericht für Aluminium-Gehäuse Auftrag 4912 erstellen. "
        "Maße laut Zeichnung Rev. C prüfen, QS-Freigabe einholen.",
        "urgent",
        "in_progress",
        0,
        "Produktion",
        "CNC-Fräse 01",
        "dirk.hartmann",
    ),
    (
        "Montagelinie 05 – Rüstplan Typ W44 abstimmen",
        "Umrüstung von Typ W42 auf W44 für Nachtschicht vorbereiten. "
        "Greifer-Set aus Lager holen, Rüstblatt aushängen.",
        "soon",
        "open",
        1,
        "Produktion",
        "Montagelinie 05",
        None,
    ),
    (
        "Spritzgussanlage 04 – Granulat PA6 nachfüllen",
        "Materialbehälter Anlage 04 unter 20 kg-Grenze. "
        "Silo-Station 3 befüllen, Chargenprotokoll in SAP buchen.",
        "soon",
        "done",
        -1,
        "Produktion",
        "Spritzgussanlage 04",
        "ayse.demir",
    ),
    (
        "Verpackungsanlage 06 – Etikettierprogramm aktualisieren",
        "Neues Kundenlogo für Auftrag DE-5003 laden. "
        "Testdruck auf 5 Etiketten, Freigabe durch Schichtleiter.",
        "normal",
        "open",
        3,
        "Produktion",
        "Verpackungsanlage 06",
        None,
    ),
    (
        "Förderband Linie A – Ausschussquote Frühschicht erfassen",
        "Ausschussteile zählen und Fehlerart kategorisieren. "
        "Erfassung im Shopfloor-Board bis Schichtende.",
        "normal",
        "done",
        -3,
        "Produktion",
        "Förderband Linie A",
        "stefan.braun",
    ),
    (
        "Roboterzelle 09 – Vakuumsauger wechseln Station 2",
        "Vakuumsauger an Greiferstation 2 verschlissen (Haltekraft < 80 %). "
        "Set aus Lager entnehmen, Tausch im Stillstand.",
        "soon",
        "in_progress",
        1,
        "Produktion",
        "Roboterzelle 09",
        "tobias.zimmermann",
    ),
    (
        "CNC-Drehmaschine 02 – Präzisionswellen Losgröße 80",
        "Fertigungslos PW-2024-080 anlegen. "
        "Spannmittel-Wechsel, Nullpunkt einmessen, Erstmaß abnehmen.",
        "normal",
        "open",
        5,
        "Produktion",
        "CNC-Drehmaschine 02",
        None,
    ),
    (
        "Montagelinie 05 – Kanban-Karten Sensoren prüfen",
        "Bestand an induktiven Sensoren am Kanban-Regal prüfen. "
        "Unterschreitung Meldebestand → Bestellkarte in Einkaufsbox.",
        "normal",
        "done",
        -4,
        "Produktion",
        "Montagelinie 05",
        "claudia.werner",
    ),
    (
        "Verpackungsanlage 06 – Verpackungsmaterial Auftrag 5021",
        "Kartons 400×300×200 für Auftrag 5021 (240 Stück) bereitstellen. "
        "Lagerort B-04 prüfen, fehlende Menge nachbestellen.",
        "soon",
        "open",
        2,
        "Produktion",
        "Verpackungsanlage 06",
        None,
    ),
    (
        "Prüfstand 08 – End-of-Line-Prüfung Schicht C dokumentieren",
        "Prüfergebnisse aller 48 Baugruppen aus Nachtschicht im System erfassen. "
        "3 NIO-Teile separat lagern und Rückmeldung an QS.",
        "normal",
        "open",
        0,
        "Produktion",
        "Prüfstand 08",
        None,
    ),
    # Verwaltung
    (
        "Wartungsverträge Q2 – Ablauf prüfen",
        "Verträge für CNC-Fräse 01, Hydraulikpresse 03 und Roboterzelle 09 laufen im Juni aus. "
        "Verlängerungsangebote einholen und Vergabereport erstellen.",
        "soon",
        "open",
        6,
        "Verwaltung",
        None,
        None,
    ),
    (
        "Ersatzteil-Rechnungen März klären",
        "3 Rechnungen von Parker, SKF und Igus ohne Bestellbezug. "
        "Kostenstellen-Zuordnung prüfen, Buchungsbeleg an Buchhaltung.",
        "normal",
        "in_progress",
        2,
        "Verwaltung",
        None,
        "petra.weiss",
    ),
    (
        "Lieferantenstammdaten aktualisieren",
        "Neue Bankdaten von Sandvik Coromant und Atlas Copco in SAP einpflegen. "
        "Änderungsbeleg unterschreiben lassen.",
        "normal",
        "done",
        -2,
        "Verwaltung",
        None,
        "frank.lorenz",
    ),
    (
        "Monatsreport Anlagenverfügbarkeit April",
        "OEE-Kennzahlen aus Schichtprotokollen zusammenführen. "
        "Bericht bis 5. des Monats an Werksleitung.",
        "soon",
        "open",
        4,
        "Verwaltung",
        None,
        None,
    ),
    (
        "Schulungsnachweise 2026 abgleichen",
        "Prüfen welche Mitarbeiter Wiederholungsschulung (UVV, Stapler, Ersthelfer) benötigen. "
        "Liste an Personalreferentin, Termine blockieren.",
        "normal",
        "open",
        10,
        "Verwaltung",
        None,
        None,
    ),
    # IT
    (
        "Backup-Status Produktionsserver prüfen",
        "Backup-Job VM-PROD-01 schlug laut Monitoring 2× fehl. "
        "Log auswerten, freien Speicher prüfen, Backup manuell anstoßen.",
        "urgent",
        "in_progress",
        0,
        "IT",
        None,
        "ralf.bergmann",
    ),
    (
        "WLAN-Ausleuchtung Halle 2 nachmessen",
        "Schichtleiter meldet Verbindungsabbrüche am Tablet Linie A. "
        "Site-Survey mit NetSpot durchführen, Access Point Pos. anpassen.",
        "soon",
        "open",
        3,
        "IT",
        None,
        None,
    ),
    (
        "VPN-Zugriff Rufbereitschaft testen",
        "Monatstest gemäß IT-Richtlinie: alle 5 Rufbereitschafts-Zugänge einwählen. "
        "Ergebnis im IT-Betriebshandbuch dokumentieren.",
        "normal",
        "done",
        -1,
        "IT",
        None,
        "sonja.brandt",
    ),
    (
        "Scanner-Firmware Lager aktualisieren",
        "Honeywell-Scanner Lager A und B auf Firmware 3.2.1 bringen. "
        "Update-Paket liegt auf Netzlaufwerk \\\\srv01\\updates\\scanner bereit.",
        "normal",
        "open",
        5,
        "IT",
        None,
        None,
    ),
    (
        "USV-Selbsttest auswerten",
        "Wöchentlicher Selbsttest der USV im Schaltschrank Halle 1. "
        "Batteriezustand und Laufzeit protokollieren, Wert < 8 min → Tausch melden.",
        "normal",
        "done",
        -6,
        "IT",
        None,
        "ralf.bergmann",
    ),
]

# ---------------------------------------------------------------------------
# Fehlerkatalog
# ---------------------------------------------------------------------------

ERROR_DEFINITIONS = [
    # (fehlercode_suffix, titel, ursache, lösung, maschinenname)
    (
        "E-101",
        "Sensor liefert kein Signal",
        "Kabelbruch, verschmutzter Sensor oder falscher Einbauabstand.",
        "Sensor reinigen, Abstand laut Datenblatt prüfen, Kabel auf Durchgang messen.",
        "Montagelinie 05",
    ),
    (
        "E-102",
        "Motor überlastet",
        "Blockierter Antrieb, erhöhte Lagerreibung oder falsche Umrichterparameter.",
        "Antrieb von Hand drehen, Lager abhorchen, I-max-Parameter prüfen.",
        "Förderband Linie A",
    ),
    (
        "E-103",
        "Druck fällt ab",
        "Leckage an Schlauch oder Verschraubung, defektes Ventil oder Filter zugesetzt.",
        "Lecktest mit Sprühkreide, Ventilspule messen, Filter tauschen.",
        "Hydraulikpresse 03",
    ),
    (
        "E-104",
        "Temperatur außerhalb Toleranz",
        "Heizkreis defekt, Kühlwasserdurchfluss zu gering oder Regler falsch parametriert.",
        "Heizzone per Messzange prüfen, Kühlkreis entlüften, Sollwert kontrollieren.",
        "Spritzgussanlage 04",
    ),
    (
        "E-105",
        "Kommunikation zur Steuerung gestört",
        "Netzwerkfehler, SPS-Koppler überhitzt oder IP-Konflikt im Subnetz.",
        "Switch-Port LED prüfen, SPS-Diagnose aufrufen, IP-Tabelle sichten.",
        "CNC-Fräse 01",
    ),
    (
        "E-106",
        "Not-Halt-Kreis offen",
        "Türkontakt nicht geschlossen, Not-Halt-Taster rastet nicht oder "
        "Sicherheitsrelais ausgefallen.",
        "Alle Schutztüren schließen, Taster entriegeln, Relaisausgänge messen.",
        "Montagelinie 05",
    ),
    (
        "E-107",
        "Werkzeug nicht referenziert",
        "Referenzfahrt nach Stromausfall ausgeblieben oder Endschalter verschmutzt.",
        "Referenzfahrt starten, Endschalter reinigen, Positions-Offset kontrollieren.",
        "CNC-Fräse 01",
    ),
    (
        "E-108",
        "Barcode nicht lesbar",
        "Etikett beschädigt, Scannerlinse verschmutzt oder Beleuchtung ausgefallen.",
        "Linse reinigen, Etikett neu drucken, LED-Beleuchtung prüfen.",
        "Verpackungsanlage 06",
    ),
    (
        "E-109",
        "Vakuum zu niedrig",
        "Sauger verschlissen, Schlauch undicht oder Magnetventil klemmt.",
        "Sauger auf Risse prüfen, Druckverlusttest, Ventil durchschalten.",
        "Roboterzelle 09",
    ),
    (
        "E-110",
        "Materialstau erkannt",
        "Bauteil verkippt in Führung, Bandlauf dejustiert oder Sensor zu nah.",
        "Stau beseitigen, Führungsbreite prüfen, Sensor nachjustieren.",
        "Förderband Linie A",
    ),
    (
        "E-111",
        "Achse folgt Sollwert nicht",
        "Geberfehler, mechanische Verspannung oder Lagerspiel zu groß.",
        "Schlepp-Fehlergrenze auslesen, Geber tauschen, Mechanik nachprüfen.",
        "CNC-Drehmaschine 02",
    ),
    (
        "E-112",
        "Ölstand niedrig",
        "Leckage am Zylinder oder Schlauch, normaler Verbrauch überschritten.",
        "Anlage sicher stoppen, Leckage lokalisieren, Öl nachfüllen.",
        "Hydraulikpresse 03",
    ),
    (
        "E-113",
        "Prüfergebnis instabil",
        "Schlechte Kontaktierung, verschlissener Adapter oder Messleitung gebrochen.",
        "Kontakte reinigen, Leitungswiderstand messen, Adapter tauschen.",
        "Prüfstand 08",
    ),
    (
        "E-114",
        "Absaugung meldet Unterdruck",
        "Filter zugesetzt, Klappe klemmt oder Schlauch geknickt.",
        "Filter reinigen oder tauschen, Klappe manuell öffnen, Schlauchführung prüfen.",
        "Laserbeschrifter 10",
    ),
    (
        "E-115",
        "Rüstdaten fehlen",
        "Auftragsdaten noch nicht an Maschinensteuerung übertragen oder falsches Rezept gewählt.",
        "Auftrag im MES öffnen, Rezept manuell laden, Parametrierung bestätigen.",
        "CNC-Fräse 01",
    ),
    (
        "E-116",
        "Druckluftqualität schlecht",
        "Trockner abgeschaltet, Kondensatableiter defekt oder Filter gesättigt.",
        "Taupunkt messen, Ableiter testen, Filter wechseln.",
        "Kompressorstation 07",
    ),
    (
        "E-117",
        "Schutzzaun offen",
        "Türschalter defekt, Verriegelung klemmt oder Zuhaltung nicht bestromt.",
        "Schalter tauschen, Zuhaltespannung messen, Verriegelungsbolzen reinigen.",
        "Roboterzelle 09",
    ),
    (
        "E-118",
        "Füllstand Material niedrig",
        "Nachfüllung vergessen oder Sensor liefert Fehlmeldung.",
        "Behälter befüllen, Sensor-Schwelle prüfen, Meldung quittieren.",
        "Spritzgussanlage 04",
    ),
    (
        "E-119",
        "Kalibrierung abgelaufen",
        "Kalibrierintervall laut Prüfplan überschritten.",
        "Prüfmittel sperren, Kalibrierung beauftragen, Ergebnis einpflegen.",
        "Prüfstand 08",
    ),
    (
        "E-120",
        "Qualitätsgrenze überschritten",
        "Verschlissenes Werkzeug, veränderte Rohmaterialcharge oder Prozess-Drift.",
        "Werkzeug tauschen, Charge sperren, Prozessparameter zurücksetzen.",
        "CNC-Fräse 01",
    ),
]
