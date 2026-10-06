# Neues Testament (Johannes 1-10, Epheser) – Stilblatt für die berndeutschen Entwürfe

Stand: 06.10.2026. Dieses Blatt ist **eigenständig**: Es enthält absichtlich keine Textstellen aus Bietenhards Johannes oder Epheser.

## Quarantäne – unbedingt einhalten

- Bietenhards **Johannes-Evangelium** und **Epheserbrief** sind unter Quarantäne und dürfen weder gelesen noch gesucht noch aus dem Gedächtnis verwendet werden. Das gilt auch für jede andere berndeutsche oder schweizerdeutsche Übersetzung dieser zwei Bücher.
- **Nicht öffnen:** die Notizen und Stilblätter unter `draft/ch-de-be/ruth/`, `draft/ch-de-be/jona/` und `draft/ch-de-be/1mos/`. Sie enthalten einzelne Zitate aus Bietenhards Johannes.
- Kein Web-Zugriff auf berndeutsche Bibeltexte.

## Quellen

1. **Grundtext (übersetzt wird aus ihm):** `orig_gr/johNNN.txt`, `orig_gr/ephNNN.txt`. Das ist die Berean Greek Bible (BGB), der griechische Text, aus dem die BSB übersetzt ist. Eine Zeile pro Vers, `K:V griechischer Text`. Die BGB-Zeichen ‹…› (unsichere Wörter), 〈…〉 und ⇔ (Wortstellung) bleiben im Grundtext stehen. Die BGB-Textnoten (Varianten NA/BYZ/TR/WH, AT-Zitate) stehen in `orig_gr/…_bgb_notes.txt`.
2. **Einzige Hilfsübersetzung:** BSB (`BSB/johNNN.txt`, `BSB/ephNNN.txt`, mit `{T: …}`-Fussnoten). Sie dient nur als Entscheidungshilfe zum Griechischen; im Zweifel folgt man der BSB-Deutung.
3. **Nur für Stil und Wortschatz:** Bietenhards Bärndütschi Bibel unter `Berndeutsche Bibel/text/*.txt` (alle NT-Bücher ausser Johannes und Epheser). Jede Wortwahl wird mit einer Häufigkeitsabfrage (Python `collections.Counter` über diese Dateien) geprüft. Bietenhards Wort ist zu bevorzugen, wo es eines gibt.

## Grundsätze (übernommen aus den AT-Projekten Rut, Jona, Genesis)

- **Sauberer Text:** keine Inline-Noten im Bibeltext.
- **Notizen** auf **Hochdeutsch** in `…NNN_notes.md`, für die Durchsicht.
- **Fussnoten** wie in der BSB, auf **Berndeutsch**, in einer **separaten Datei** `…NNN_footnotes.txt`, nur bei Bedarf. Format: Kopfzeilen, dann eine Zeile pro Fussnote `vN Stichwort: Text`. Inhalt: »Oder: …«-Alternativen, Namensdeutungen, Quellenangaben bei AT-Zitaten (Bietenhards Format: »5Mo 6,5«, »Jes 40,3«, »Ps 69,10«) sowie wichtige Textvarianten, z. B. »Vers 4 fählt i de ältischte Handschrifte«.
- **Textkritik:** übersetzt wird der BGB-Text. Wo die BSB eine Fussnote zu einer Variante hat, kommt eine berndeutsche Fussnote dazu. Eine ausgelassene Versnummer (z. B. Joh 5,4) erscheint im Text nicht. Joh 7,53-8,11 wird übersetzt (die BGB hat ihn), mit Fussnote.
- **Gottesbezeichnungen:** Θεός = Gott, Κύριος = **der Herr** (auch in AT-Zitaten: Der griechische Text sagt *Kyrios*, Bietenhard schreibt in AT-Zitaten »der Herr«). Χριστός = **Chrischtus** (Bietenhard 457× gegenüber »Christus« 16×). Πνεῦμα ἅγιον = der heilig Geischt.
- **Zahlen** in Wörtern wie Bietenhard; **Masse** im Bietenhard-Stil: Einheit + ungefähre heutige Grösse in Klammern, z. B. »zwänzg Chlafter (36 m)«; bei Hohlmassen wird in Liter umgerechnet.
- **Namen** mit Artikel (»der Petrus«, »d Maria«), in Bietenhards Formen, wo sie im erlaubten Korpus vorkommen.

## Dateien und Layout

```
!!<Reifegrad: Entwurf>!!
!!<Übersetzung: Maschinenentwurf aus dem griechischen Grundtext (orig_gr/johNNN.txt, Berean Greek Bible), abgeglichen mit der Berean Standard Bible>!!
!!<Exegetische Bearbeitung: Noch nicht erfolgt>!!
!!<Literarische Prüfung: Noch nicht erfolgt>!!
!!<Datum dieser Version: 06.10.2026>!!

===Ds Johannes-Evangelium, Kapitel N===        (bzw. ===D Brief a d Epheser, Kapitel N===)


==Überschrift im Bietenhard-Stil (berndeutsch, Satzform)==

v1 Fortlaufende Prosa mit Versmarkern inline … v2 …
```

- Die Titel sind nach Bietenhards Mustern im erlaubten Korpus gebildet (»Ds Matthäus-Evangelium«, »D Brief a d Galater«).
- Ausgabe nach `draft/ch-de-be/joh/johNNN.txt` bzw. `draft/ch-de-be/eph/ephNNN.txt` (+ `_notes.md`, + `_footnotes.txt`).
- Nach dem Schreiben `python3 scripts/wrap_draft.py <datei>` ausführen (Umbruch ca. 100 Zeichen, vN bleibt am Text). Danach prüfen, dass die vN-Marker genau den Versen in `orig_gr/` entsprechen (fehlende Verse dort fehlen auch im Entwurf).
- Anführungszeichen: „…“, innere Rede ‚…‘.
- Poesie (`//1` / `//2`-Zeilen) nur, wo die BSB poetisch setzt, z. B. bei längeren AT-Zitaten oder Hymnen.

## Feste Wiedergaben (aus dem erlaubten Korpus belegt)

| Griechisch | Berndeutsch | Bietenhard-Häufigkeit |
|---|---|---|
| Χριστός | Chrischtus | 457× |
| Κύριος | der Herr | 571× |
| Πνεῦμα | Geischt | 310× |
| λόγος | Wort | 127× |
| φῶς / σκοτία | Liecht / Fyschteri | 57× / 23× |
| κόσμος | Wält | 172× |
| ἀλήθεια | Wahrheit | 66× |
| χάρις | Gnad | 116× |
| δόξα | Herrlechkeit | 91× |
| ζωὴ αἰώνιος | ds ewige Läbe | Läbe 218×, ewige 47× |
| πιστεύω / πίστις | gloube / Gloube | 52× / 275× |
| ἀγάπη | Liebi | 177× |
| εἰρήνη | Fride | 91× |
| μαθηταί | Jünger | 208× |
| Ἰουδαῖοι | d Jude | 107× |
| ἱερόν / ναός | Tämpel | 108× |
| σημεῖον | Zeiche | 55× |
| ἐκκλησία | Gmeind | 77× |
| μυστήριον | Gheimnis | 19× |
| σῶμα / κεφαλή | Lyb / **ds Houpt** (Christus als Haupt; Kol 1,18), sonst Chopf | 92× / 5× / 53× |
| ἁμαρτία | Sünd | 139× |
| ἀπόστολος | Aposchtel | 53× |
| ὁ υἱὸς τοῦ ἀνθρώπου | der Mönschesuhn | 65× |
| ἀμνός | Lamm | 36× |

| ἀμὴν ἀμὴν λέγω ὑμῖν | Würklech, würklech, i cha nech säge: | entschieden 06.10.2026 |
| ἅγιοι (Gläubige) | d Chrischte | entschieden 06.10.2026 |
| γογγύζω | mule / gmulet | entschieden 06.10.2026 |

Alles Weitere (z. B. ἀμὴν ἀμὴν λέγω ὑμῖν, ποιμήν, αὐλή, βάπτισμα, κληρονομία, εὐλογητός) wird aus dem erlaubten Korpus abgeleitet und im Notizfile belegt.

## Notizfile (`…NNN_notes.md`, Hochdeutsch)

1. Was der Entwurf ist (1-2 Zeilen)
2. Textgrundlage: BGB-Varianten in diesem Kapitel und wie sie behandelt sind
3. Tabelle *Vers · Griechisch · Berndeutsch · BSB · Kommentar*, für bewusste Entscheidungen
4. Exegetische Beobachtungen, nummeriert
5. Mundart und Stil: welche Wörter bei Bietenhard belegt sind (mit Anzahl), welche nicht
6. Offene Fragen
