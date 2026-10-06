# Ds Buech Rut – Arbeitsstilblatt für die berndeutschen Entwürfe (`draft/ch-de-be/ruth/`)

Stand: 02.10.2026 · gilt sinngemäss auch für Jona (`draft/ch-de-be/jona/`)

## Grundsätze

- Übersetzt wird **direkt aus dem Hebräischen** (`orig/ruthNNN.txt`, klauselweise masoretischer Text).
- Einzige Hilfsübersetzung: **Berean Standard Bible** (`BSB/rutNNN.txt`). Sie dient nur dazu, Entscheidungen zu kippen, wo das Hebräische mehrere Wiedergaben zulässt. SVK wird diesmal **nicht** verwendet.
- Zielsprache: **Berndeutsch**, Stilvorbild ist die Bärndütschi Bibel von Rudolf Bietenhard (NT, `Berndeutsche Bibel/text/`). Wortschatz und Schreibweise werden dort abgelesen; wo Bietenhard ein Wort nicht hat, wird die geläufige Berner Form gewählt und im Notizfile vermerkt.
- **Sauberer Text:** keine Inline-Noten (`{T:}`, `{E:}`, `{H:}`, `{N:}`) im Bibeltext. Alle Übersetzungs- und exegetischen Hinweise stehen ausschliesslich in `ruthNNN_notes.md` (auf **Hochdeutsch**).
- Pro Kapitel genau **eine** Fassung (`ruthNNN.txt`) – kein Zwei-Spur-System wie bei Josua.

## Dateien pro Kapitel

- `ruthNNN.txt` – der berndeutsche Entwurf
- `ruthNNN_notes.md` – Notizen für die Durchsicht (Hochdeutsch)
- `ruthNNN_footnotes.txt` – bei Bedarf: Fussnoten für Leser wie in der BSB (berndeutsch, separat vom Text, Format `vN Stichwort: Text`), z. B. Namensdeutungen
- übergreifend: `ruth_style_guide.md` (dieses Blatt), `ruth_review_overview.md` (offene Punkte über alle Kapitel)

## Dateikopf und Layout

```
!!<Reifegrad: Entwurf>!!
!!<Übersetzung: Maschinenentwurf aus dem Grundtext (orig/ruthNNN.txt), abgeglichen mit der Berean Standard Bible>!!
!!<Exegetische Bearbeitung: Noch nicht erfolgt>!!
!!<Literarische Prüfung: Noch nicht erfolgt>!!
!!<Datum dieser Version: 02.10.2026>!!

===Ds Buech Rut, Kapitel N===


==Überschrift im Bietenhard-Stil==

v1 Fortlaufende Prosa mit Versmarkern inline … v2 … Zeilenumbruch bei ca. 100 Zeichen.
```

- Fortlaufende Prosa wie Bietenhard (nicht klauselweise `//N` wie das dänische Rut).
- Überschriften `==…==` sind redaktionell, berndeutsch, in Satzform wie bei Bietenhard (»D Geburt vo Jesus wird aagseit«, »Jesus findet syni erschte Jünger«).
- Anführungszeichen wie Bietenhard: `„…“`, innere Rede `‚…‘`.
- Bibelstellen (nur im Notizfile nötig) im Bietenhard-Format: `(5Mo 25,5-10)`, `(1Mo 38)`.

## Feste Wiedergaben

| Hebräisch | Berndeutsch | Begründung |
|---|---|---|
| יהוה | **der HERR** (vom HERR, em HERR) | Entscheid 02.10.2026: Grossbuchstaben machen den Gottesnamen sichtbar (wie HERREN im dänischen Projekt, Luther, Zürcher). Bietenhard selbst schreibt in AT-Zitaten »der Herr«. |
| אלהים | Gott | |
| שַׁדַּי | der Allmächtig | Bietenhard »Allmächtig« (2×) |
| חֶסֶד | Tröiji (… d Tröiji halte / erwyse) | Bietenhard »Tröiji« (4×); Schlüsselwort 1,8; 2,20; 3,10 – überall gleich halten |
| גֹּאֵל / גאל | **Löser** / uslöse (mit Lösrächt) | Bei Bietenhard nicht belegt; deutsche Fachtradition (Luther, Zürcher »Löser«). Alternative »Erblöser«, »Verwandte mit Lösrächt« – offen |
| מֹואֲבִיָּה | d Moabitere / moabitischi Froue | |
| כַּלָּה | Schwigertochter, Pl. Schwigertöchtere | Bietenhard »Schwigertochter«, »Töchtere« |
| חָמוֹת | Schwigermueter | Bietenhard |
| שְׂעֹרִים / חִטִּים | Gärschte / Weize | Bietenhard »Gärschte«, »Weize« |
| קָצִיר | Ärn | Bietenhard »Ärn« |
| שִׁבֳּלִים | Ähri | Bietenhard »Ähri« |
| גֹּרֶן | Tenn | Bietenhard »Tenn« |
| נשׁק | es Müntschi gä | Bietenhard Lk 15,20 |
| בכה (mit נשׂא קול) | lut aafa briegge | Bietenhard »briegge« (18×) |
| הִנֵּה | lue / lueget | |
| זִקְנֵי הָעִיר | (Kap. 4 – zu entscheiden: »d Eltischte« vs. »d Ratsherre vo der Stadt«) | Bietenhard »Ratsherre« (31×) für πρεσβύτεροι |

## Namen

Mit Artikel wie bei Bietenhard (»der Boas«, »d Rut«), Formen aus Mt 1,3-6 übernommen, wo vorhanden:

| Hebräisch | Berndeutsch | Quelle |
|---|---|---|
| רוּת | d Rut | Mt 1,5 |
| בֹּעַז | der Boas | Mt 1,5 |
| עוֹבֵד | der Obed | Mt 1,5 |
| יִשַׁי | der Isai | Mt 1,5 |
| דָּוִד | der David | |
| פֶּרֶץ, חֶצְרוֹן, רָם, עַמִּינָדָב, נַחְשׁוֹן, שַׂלְמָה/שַׂלְמוֹן | der Perez, der Hezron, der Ram, der Amminadab, der Nachschon, der Salmon | Mt 1,3-5 |
| תָּמָר | d Tamar | Mt 1,3 |
| נָעֳמִי | d Noomi | Luther/Zürcher |
| מָרָא | Mara | |
| אֱלִימֶלֶךְ | der Elimelech | Luther/Zürcher |
| מַחְלוֹן, כִּלְיוֹן | der Machlon, der Kiljon | Luther/Zürcher |
| עָרְפָּה | d Orpa | |
| בֵּית לֶחֶם יְהוּדָה | Betlehem z Juda | Bietenhard »Betlehem« (8×) |
| אֶפְרָתִים / אֶפְרָתָה | Efratiter / Efrata | |
| מוֹאָב | Moab, ds Land Moab | |
| רָחֵל, לֵאָה | d Rahel, d Lea | |
| יְהוּדָה | Juda | |

## Zahlen

Wie Bietenhard ausgeschrieben: eis/ei, zwee (m.)/zwo (f.)/zwöi (n.), drei, vier, füf, sächs, sibe, acht, nüün, zäh (attributiv auch »zäche«).

## Notizfile (`ruthNNN_notes.md`), Hochdeutsch

1. Was der Entwurf ist (1-2 Zeilen)
2. Tabelle *Vers · Hebräisch · Berndeutsch · BSB · Kommentar* – wo die Wiedergabe eine bewusste Entscheidung ist
3. Exegetische Beobachtungen, nummeriert, mit Versangabe
4. Mundart-/Stilpunkte (Wörter, die bei Bietenhard nicht belegt sind)
5. Offene Fragen für die Durchsicht
