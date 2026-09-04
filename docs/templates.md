# Templates und Sprachen

[Projektübersicht und Schnellstart](../README.md) · [Dokumentationsübersicht](README.md)

## Ansagetexte festlegen

Globale Texte stehen unter `announcements.half_hour.template` und
`announcements.full_hour.template`. Ein Standort kann sie unter
`locations.<id>.announcements` überschreiben. Mit `enabled: false` lässt sich
eine der beiden Ansagearten deaktivieren. Die Beispiele sind Ausschnitte für
deine bestehende [Konfiguration](configuration.md).

## Template-Variablen

Templates verwenden Platzhalter in geschweiften Klammern, zum Beispiel
`Es ist {time} in {location}. Die Temperatur beträgt {temperature} Grad.`
Derzeit sind folgende Variablen implementiert:

| Variable | Inhalt und Ausgabeformat |
| --- | --- |
| `{greeting}` | Begrüßung nach lokaler Standortzeit: morgens bis 11:59 Uhr, tagsüber ab 12:00 Uhr und abends ab 18:00 Uhr; die Texte werden in der Sprachdatei unter `greetings` konfiguriert |
| `{time}` | Geplante Wiedergabezeit in Wörtern der Standortsprache, zum Beispiel `vierzehn Uhr dreißig` |
| `{hour}` | Stunde der geplanten Wiedergabe in Wörtern der Standortsprache, zum Beispiel `vierzehn` |
| `{minute}` | Minute der geplanten Wiedergabe als Zahl, zum Beispiel `30` |
| `{date}` | Lokalisiertes Datum der geplanten Wiedergabe, zum Beispiel `18. August 2026` |
| `{location}` | Konfigurierter Anzeigename des Standorts |
| `{latitude}` | Breitengrad des Standorts |
| `{longitude}` | Längengrad des Standorts |
| `{temperature}` | Vorhergesagte Temperatur in der für den Standort konfigurierten Einheit |
| `{apparent_temperature}` | Vorhergesagte gefühlte Temperatur in der für den Standort konfigurierten Einheit |
| `{dew_point}` | Vorhergesagter Taupunkt in der für den Standort konfigurierten Einheit |
| `{humidity}` | Relative Luftfeuchtigkeit in Prozent |
| `{pressure}` | Luftdruck an der Oberfläche in Hektopascal |
| `{weather_description}` | Lokalisierte Beschreibung des providerunabhängigen WMO-Wettercodes, zum Beispiel `teilweise bewölkt` |
| `{weather_code}` | Numerischer, intern vereinheitlichter WMO-Wettercode |
| `{cloud_cover}` | Bewölkungsgrad in Prozent |
| `{wind_speed}` | Windgeschwindigkeit in Kilometern pro Stunde |
| `{wind_direction}` | Windrichtung als lokalisierte Himmelsrichtung, zum Beispiel `Südwesten` |
| `{wind_direction_degrees}` | Windrichtung in Grad |
| `{wind_gusts}` | Geschwindigkeit der Windböen in Kilometern pro Stunde |
| `{precipitation}` | Vorhergesagte Niederschlagsmenge in Millimetern |
| `{precipitation_probability}` | Niederschlagswahrscheinlichkeit in Prozent |
| `{day_temperature_min}` | Tiefste Temperatur des lokalen Kalendertags in der konfigurierten Temperatureinheit |
| `{day_temperature_max}` | Höchste Temperatur des lokalen Kalendertags in der konfigurierten Temperatureinheit |
| `{day_precipitation_sum}` | Erwartete Niederschlagssumme des lokalen Kalendertags in Millimetern |
| `{day_precipitation_probability_max}` | Höchste stündliche Niederschlagswahrscheinlichkeit des lokalen Kalendertags in Prozent |
| `{day_precipitation_hours}` | Anzahl der Stunden mit erwartetem Niederschlag am lokalen Kalendertag |
| `{day_cloud_cover_mean}` | Mittlerer Bewölkungsgrad über den gesamten lokalen Kalendertag in Prozent |
| `{day_weather_description}` | Lokalisierte Beschreibung der markantesten Wetterlage des lokalen Kalendertags |
| `{day_wind_speed_max}` | Höchste Windgeschwindigkeit des lokalen Kalendertags in Kilometern pro Stunde |
| `{day_wind_gusts_max}` | Höchste Böengeschwindigkeit des lokalen Kalendertags in Kilometern pro Stunde |
| `{day_weather_summary}` | Lokalisierte Zusammenfassung aus Tageswetterlage sowie Tagesminimum und -maximum |
| `{day_cloud_summary}` | Lokalisierte, aus dem mittleren Bewölkungsgrad abgeleitete Tageszusammenfassung |
| `{day_precipitation_summary}` | Lokalisierte Zusammenfassung aus maximaler Niederschlagswahrscheinlichkeit und erwarteter Niederschlagssumme |
| `{sunrise}` | Sonnenaufgang in den Zeitwörtern der Standortsprache, zum Beispiel `fünf Uhr achtundvierzig` |
| `{sunset}` | Sonnenuntergang in den Zeitwörtern der Standortsprache |
| `{forecast_time}` | Zeitpunkt der verwendeten Wetterdaten in den Zeitwörtern der Standortsprache |
| `{warning_count}` | Anzahl der zum Wiedergabezeitpunkt aktiven DWD-Warnungen |
| `{warning_level}` | DWD-Warnstufe der höchstpriorisierten aktiven Warnung |
| `{warning_event}` | Ereignisbezeichnung der höchstpriorisierten Warnung |
| `{warning_headline}` | Überschrift der höchstpriorisierten Warnung |
| `{warning_description}` | Ausführliche Beschreibung der höchstpriorisierten Warnung |
| `{warning_instruction}` | Handlungshinweis der höchstpriorisierten Warnung |
| `{warning_start}` | Beginn der höchstpriorisierten Warnung in lokalisierten Zeitwörtern |
| `{warning_end}` | Ende der höchstpriorisierten Warnung in lokalisierten Zeitwörtern |
| `{warning_text}` | Überschriften aller aktiven Warnungen oder lokalisierter Hinweis, dass keine Warnung aktiv ist |
| `{temperature_source}` | Provider des verwendeten Temperaturwerts, zum Beispiel `dwd` |
| `{weather_source}` | Provider des verwendeten Wettercodes und der Wetterbeschreibung |
| `{warning_source}` | Provider der höchstpriorisierten aktiven Warnung |

Numerische Werte werden auf eine Nachkommastelle gerundet, überflüssige
Nachkommastellen werden entfernt und das Dezimaltrennzeichen wird lokalisiert.
Eine unbekannte Variable, eine Formatangabe wie `{temperature:.1f}` oder ein im
konkreten Forecast nicht verfügbarer verwendeter Wert bricht die Generierung
kontrolliert ab. Das bisher veröffentlichte Audio-Asset bleibt dabei erhalten.
`{warning_count}` und `{warning_text}` sind immer belegt. Die übrigen Warnfelder
sind nur verwendbar, wenn zum Wiedergabezeitpunkt mindestens eine entsprechende
Warnung aktiv ist. Bei mehreren Warnungen liefert das Modul für die einzelnen
Warnfelder die höchste Warnstufe; `{warning_text}` verbindet alle Überschriften.
Die `day_`-Variablen beziehen sich auf das lokale Kalenderdatum der geplanten
Wiedergabe. Die Tageszusammenfassungen sind vollständige Sätze und können direkt
aneinandergereiht werden, zum Beispiel:

```yaml
template: >
  Es ist {time} in {location}. {day_weather_summary}
  {day_cloud_summary} {day_precipitation_summary}
```

## Sprachen und Aussprachewörterbücher

Weatherbox liefert die Sprachen Deutsch (`de`) und Englisch (`en`) mit. Die
zugehörigen YAML-Wörterbücher liegen unter [src/weatherbox/lang/](../src/weatherbox/lang/). Sie enthalten:

- Zahlen von null bis neunzehn und die Zehner bis fünfzig
- Regeln und Ausnahmen für zusammengesetzte Zahlen
- kontextabhängige Formen wie `ein Uhr` gegenüber `eins`
- Zeit- und Datumsmuster sowie Monatsnamen
- Dezimaltrennzeichen
- Beschreibungen der providerunabhängigen WMO-Wettercodes
- Satzmuster für Wetter-, Bewölkungs- und Niederschlagszusammenfassungen
- 16 Windrichtungen

Die eingebauten Zusammenfassungen ordnen die mittlere Tagesbewölkung festen
Bewölkungsstufen und die maximale Niederschlagswahrscheinlichkeit festen
Wahrscheinlichkeitsstufen zu. Sämtliche ausgegebenen Sätze stehen unter
`summaries` in der jeweiligen Sprachdatei und können dort ersetzt werden. Bei
älteren eigenen Sprachdateien darf der Abschnitt fehlen; die übrige Sprache
bleibt dann nutzbar, während die drei Zusammenfassungsvariablen unbelegt sind.

Die Sprache kann für jeden Standort separat gewählt werden:

```yaml
localization:
  default_language: de
  # Optional: eigene vollständige YAML-Sprachdateien aus diesem Verzeichnis laden
  directory: lang

locations:
  wittstock:
    name: Wittstock
    latitude: 53.16
    longitude: 12.48
    timezone: Europe/Berlin
    temperature_unit: c
    language: de

  london:
    name: London
    latitude: 51.51
    longitude: -0.13
    timezone: Europe/London
    temperature_unit: f
    language: en
    announcements:
      full_hour:
        template: >
          It is {time} in {location}. The temperature is {temperature} degrees.
          Conditions are {weather_description}.
```

Eigene Sprachdateien müssen das vollständige Schema einer eingebauten Datei
besitzen. Eine Datei im konfigurierten `localization.directory` überschreibt eine
eingebaute Sprache mit demselben `code`; neue Codes ergänzen den Katalog. Über
`numbers.overrides` können unregelmäßige Zahlen vollständig überschrieben werden.
`time.hour_mode` unterstützt eine 12- oder 24-Stunden-Ausgabe. Ungültige oder
unvollständige Sprachdateien werden bereits beim Programmstart abgelehnt.

Templates werden bewusst nicht automatisch übersetzt. Für einen anderssprachigen
Standort muss daher ein passendes Standort-Template konfiguriert werden.
