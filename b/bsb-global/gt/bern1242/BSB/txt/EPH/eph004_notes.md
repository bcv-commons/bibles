# Epheser 4 – Notizen zum berndeutschen Entwurf

## 1. Was der Entwurf ist

Maschinenentwurf von Eph 4,1-32 aus dem griechischen Grundtext (`orig_gr/eph004.txt`, BGB), abgeglichen mit der BSB. Wortschatz und Stil nach Bietenhards erlaubtem Korpus (ohne Johannes und Epheser); Häufigkeiten unten aus einer `collections.Counter`-Abfrage über `Berndeutsche Bibel/text/*.txt` (Wortformen, ohne Gross-/Kleinschreibung). 32 Verse, vN-Marker gegen `orig_gr` geprüft.

## 2. Textgrundlage und Varianten

- **4,8** AT-Zitat Ps 68,19 (deutsche/hebräische Zählung; BSB/englisch: Ps 68:18). Die BGB-Note hat zudem »Or He says« → Fussnote »Oder: Drum seit er.« Das Zitat ist wie in der BSB poetisch (`//1`/`//2`) gesetzt. Das (καὶ) der BGB in Klammern ist mit »und« übersetzt.
- **4,9** BYZ/TR: κατέβη **πρῶτον** (»zuerst hinabgestiegen«) – BSB-Fussnote → berndeutsche Fussnote.
- **4,14** κυβείᾳ* – das Sternchen der BGB markiert nur eine Lesart-/Akzentfrage, keine BSB-Fussnote; nicht vermerkt.
- **4,26** AT-Zitat Ps 4,5 (deutsch; BSB/englisch Ps 4:4). BSB-Alternative »In your anger do not sin« als »Oder«-Fussnote. [τῷ] in eckigen Klammern: ohne Einfluss auf die Übersetzung.

## 3. Bewusste Entscheidungen

| Vers | Griechisch | Berndeutsch | BSB | Kommentar |
|---|---|---|---|---|
| 1 | ὁ δέσμιος ἐν Κυρίῳ | i, wo für e Herr gfange bi | a prisoner in the Lord | »Gfangene« (9×) wäre möglich; Verbalsatz flüssiger. |
| 1 | ἀξίως περιπατῆσαι τῆς κλήσεως | Füeret es Läbe, wo der Beruefig wärt isch | walk in a manner worthy of the calling | περιπατέω durchgehend »läbe / ds Läbe füere« (Gal 5,16 Bietenhard). |
| 2 | ταπεινοφροσύνη, πραΰτης, μακροθυμία | bescheide, fründlech, geduldig | humility, gentleness, patience | Adjektivisch aufgelöst; Bescheideheit 6×, Fründlechkeit 4×, Geduld 27×. |
| 3 | ἑνότης / σύνδεσμος | Einigkeit / Band | unity / bond | Einigkeit nur 1× (profan), aber naheliegend; auch 4,13. |
| 7 | κατὰ τὸ μέτρον τῆς δωρεᾶς | je nach em Määs, wo Chrischtus se usteilt | according to the measure of the gift | Määs 16×. |
| 8 | ᾐχμαλώτευσεν αἰχμαλωσίαν | het Gfangeni mit sech gfüert | He led captives away | |
| 9 | εἰς τὰ κατώτερα μέρη τῆς γῆς | i di undere Gägete vo der Ärde | to the lower parts of the earth | Exegetisch offen (Unterwelt oder Erde selbst, gen. appositivus) → »Oder«-Fussnote. |
| 11 | εὐαγγελισταί, ποιμένες | Evangelischte, Hirte | evangelists, pastors | Evangelischt 1× (Apg 21,8); »Hirte« (8×) statt »Pfarrer«, weil Bild bewahrt. |
| 12 | τῶν ἁγίων | d Chrischte | the saints | Siehe Abschnitt 5 (ἅγιοι). |
| 13 | εἰς ἄνδρα τέλειον | zum erwachsene, vollkommene Mönsch | as we mature | ἀνήρ inklusiv mit »Mönsch«; Erkenntnis 3×. |
| 14 | κλυδωνιζόμενοι … ἀνέμῳ | vo de Wälle hin und här gworfe … vo jedem Luft | tossed by the waves … every wind | »Luft« = Wind bei Bietenhard (Mt 11,7; Jak 1,6). |
| 14 | κυβεία, πανουργία, μεθοδεία τῆς πλάνης | falsches Spil, Hinderlischt, verfüere | clever cunning … deceitful scheming | Hinderlischt 1× (Lk 20,23 = πανουργία). |
| 16 | διὰ πάσης ἁφῆς τῆς ἐπιχορηγίας | dür jedes Glänk, wo ne versorget | by every supporting ligament | Glänk 1× (Hebr 4,12). Satz frei gegliedert, um Kol 2,19 nicht nachzubilden. |
| 17 | μαρτύρομαι | bezüge’s | insist | bezüge (Apg 10,42; 20,24). |
| 17 | τὰ ἔθνη | d Heide | the Gentiles | Heide 63×. |
| 19 | ἀσέλγεια, ἀκαθαρσία, πλεονεξία | Usgürte, Dräck, nie gnue ha | sensuality, impurity, craving | Usgürte = ἀσέλγεια bei Bietenhard (Gal 5,19; Röm 13,13). Dräck = ἀκαθαρσία (Gal 5,19; Kol 3,5). |
| 20 | ἐμάθετε τὸν Χριστόν | heit Chrischtus … lehre gchenne | came to know Christ | Bietenhard-Wendung (Kol 1,6). |
| 22/24 | ἀποθέσθαι / ἐνδύσασθαι τὸν … ἄνθρωπον | der alt Mönsch abzie / der nöi Mönsch aalege | put off / put on | Kleidermetapher: abzie/aalege wie Röm 13,12. |
| 26 | Ὀργίζεσθε | Wärdet töub | Be angry | Adjektiv »töub/toub« im Korpus nur Offb 11,18 (»toub worde«); im zweiten Satz Nomen Töubi (22×). |
| 29 | λόγος σαπρός / ἵνα δῷ χάριν | kes wüeschts Wort / Gnad bringt | unwholesome talk / bringing grace | χάρις = Gnad beibehalten. |
| 31 | πικρία … κραυγή … βλασφημία … κακία | Verbitterig, Wuet, Töubi, Gschrei, Läschtere, Bösi | bitterness … malice | »Bitterkeit« 0×, Verbitterig 3× (Hebr 3). |
| 32 | εὔσπλαγχνοι / χαριζόμενοι | barmhärzig / vergäbet enand | tenderhearted / forgiving | |

## 4. Exegetische Beobachtungen

1. 4,1-6: die siebenfache »ei(n)«-Reihe ist bewusst mit »ei einzige« in v4 eröffnet (Bietenhard: »ei einzige Lyb«, Röm 12,5; 1Kor 12,12) und dann knapp weitergeführt.
2. 4,8: Paulus zitiert Ps 68 abweichend vom MT/LXX (»gab« statt »empfing«); übersetzt wird der Wortlaut des Epheserbriefs.
3. 4,11-12: BSB versteht v12 als eine Zielkette (die Heiligen ausrüsten → für Dienstwerk → Aufbau des Leibes). Der Entwurf folgt dem mit neuem Satz (»Die sölle d Chrischte usrüschte …«).
4. 4,15: ἀληθεύοντες ἐν ἀγάπῃ = »d Wahrheit säge i der Liebi« (BSB »speaking the truth«).
5. 4,26: Imperativ nach LXX Ps 4,5; als Konzession verstanden (»Wenn ihr zürnt«) in der Fussnote.

## 5. Mundart und Stil

- Feste Wiedergaben (laut Stilblatt und Auftrag): Gmeind, Lyb (92×), Chopf (53×; Bietenhard hat in Kol 1,18; 2,10 auch »Houpt« 5×, aber nach Vorgabe Chopf), Gnad, Gloube, Liebi, Chrischtus, der Herr.
- **ἅγιοι:** Bietenhard übersetzt die »Heiligen« in den Briefen meist mit **»d Chrischte«** (Chrischte 51×: Röm 15,25.26; 16,15; 1Kor 6,2; 16,1; 2Kor 8,4; 13,12; Phil 1,1; Phlm 5.7; Hebr 6,10), seltener »syni Heilige« (Kol 1,12; 3,12; 1Thess 3,13; 2Thess 1,10). Der Entwurf verwendet daher »d Chrischte« (4,12; 5,3; 6,18). **Abgleich mit Kap. 1-3 nötig.**
- Belegt: Beruefig 4×, bescheide 8×, Toufi 16×, Määs 16×, Hirte 8×, Wälle 7×, Glid/Glider 7×/22×, Glüscht 25×, Lugi 7×, Mitmönsch 25×, Tüüfel 31×, Glägeheit 7×, versiglet 3×, Erlösig 1×, Wuet 6×, Gschrei 1×, Läschtere 5×, Bösi 23×, barmhärzig 6×.
- Nicht belegt (Mundartbildungen): Evangelischte (nur Sg.), zämepasst, zämehet, härewachse, zuegmässe, versorget, töub (Adj.; nur »toub« 1×).

## 6. Offene Fragen

1. ἅγιοι = »d Chrischte« – deckt sich mit dem Entwurf zu Kap. 1-3 (dort »Chrischte«, nur 1,18; 2,19 »Heilige«).
5. **κεφαλή: Chopf vs. Houpt.** Kap. 4-5 folgen Stilblatt/Auftrag (»Chopf«: 4,15; 5,23). Der Entwurf zu Kap. 1-3 hat jedoch »Houpt« gewählt (Bietenhard Kol 1,18; 2,10). Muss vereinheitlicht werden.
2. 4,9 κατώτερα μέρη: Text bleibt mehrdeutig; ist »undere Gägete« zu nah an »Unterwelt«?
3. 4,13 ἀνὴρ τέλειος mit »Mönsch« – Bild des »Mannes« geht verloren; akzeptabel?
4. 4,26 »töub« vs. Bietenhards Schreibung »toub« (Offb 11,18).

## Nachtrag: Entscheide vom 06.10.2026 (Konsistenzprüfung, vom Auftraggeber bestätigt)

- **κεφαλή** (Christus als Haupt der Gemeinde, 1,22; 4,15; 5,23) = **ds Houpt** (Bietenhard Kol 1,18); »Chopf« nur für den wörtlichen Kopf.
- **ἅγιοι** = **d Chrischte** überall (auch 1,18; 2,19, vorher »Heilige«).
