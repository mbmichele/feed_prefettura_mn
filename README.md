# Feed RSS non ufficiale — Notizie e comunicati stampa Prefettura di Mantova

Genera un feed RSS 2.0 non ufficiale a partire da due pagine pubbliche del
sito della Prefettura di Mantova:

- https://prefettura.interno.gov.it/it/prefetture/mantova/notizie
- https://prefettura.interno.gov.it/it/prefetture/mantova/evidenza/comunicati-stampa

Le pagine di dettaglio sono state osservate sotto due prefissi diversi
(`.../notizie/<slug>` e `.../comunicati-stampa/<slug>`); lo stesso
comunicato può comparire con lo stesso slug sotto entrambi i prefissi
(alias interni del sito), quindi lo script deduplica per slug e non per URL
esatto, per evitare doppioni nel feed.

Il feed viene pubblicato tramite GitHub Pages e rigenerato periodicamente
tramite una GitHub Action, innescata da un cronjob esterno (nessuno
schedule interno alla Action).

⚠️ **Nota tecnica**: il sito ha una protezione anti-bot che restituisce 403
alle richieste "troppo semplici" (confermato dai log della prima esecuzione
reale della Action). Lo script usa quindi: una sessione
`requests.Session()` persistente, un set completo di header da browser
reale (Chrome/Windows, incluso `Sec-Fetch-*`), una visita preliminare alla
home per acquisire eventuali cookie, `Referer` impostato sulla pagina di
provenienza, e fino a 3 tentativi con backoff se riceve 403/429/503. Se
dopo un run il feed risulta ancora vuoto, guarda i log dell'Action: se il
403 persiste nonostante i ritentativi, il sito potrebbe richiedere una
verifica più sofisticata (es. JavaScript challenge) non superabile da un
semplice client HTTP — in quel caso l'unica strada resterebbe uno scraping
"headless browser" (Playwright), non incluso in questa versione.

## Struttura del repository

```
.
├── scripts/
│   └── generate_feed.py       # scraping + generazione RSS
├── docs/
│   ├── index.html             # pagina minima per GitHub Pages
│   └── feed.xml               # feed generato (committato dalla Action)
├── .github/workflows/
│   └── build-feed.yml         # Action solo workflow_dispatch
├── requirements.txt
└── README.md
```

## 1. Creazione del repository

Il repository di riferimento è:
[https://github.com/mbmichele/feed_prefettura_mn](https://github.com/mbmichele/feed_prefettura_mn)

1. Crea il repository (pubblico) su GitHub con quel nome, se non esiste già.
2. Carica tutto il contenuto di questo pacchetto nel branch `main`.

## 2. Attivazione di GitHub Pages

1. Vai su **Settings → Pages**.
2. In "Build and deployment", seleziona **Deploy from a branch**.
3. Branch: `main`, cartella: `/ (root)`.
4. Salva. Il feed sarà raggiungibile (dopo qualche minuto) su:
   `https://mbmichele.github.io/feed_prefettura_mn/docs/feed.xml`

## 3. Creazione del Personal Access Token (PAT)

Serve un PAT per permettere al cronjob esterno di innescare la Action via
API GitHub:

1. Vai su **Settings personali → Developer settings → Personal access
   tokens → Fine-grained tokens** (oppure "classic", va bene lo stesso).
2. Crea un token con permesso **Actions: Read and write** limitato al
   repository `mbmichele/feed_prefettura_mn`.
3. Copia il token: ti servirà per configurare il cronjob esterno (non va
   mai salvato nel repository).

## 4. Doppio meccanismo di aggiornamento (cron interno + cron esterno)

Il workflow ha due modi per essere innescato, entrambi attivi:

- **Cron interno di GitHub Actions**: gira automaticamente ogni ora
  (`schedule: cron: "0 * * * *"` in `.github/workflows/build-feed.yml`),
  senza bisogno di configurare nulla.
- **Cron esterno** (es. cron-job.org), come innesco aggiuntivo/di backup più
  puntuale — utile perché lo schedule interno di GitHub Actions non
  garantisce l'orario esatto (può slittare di qualche minuto nei momenti di
  carico).

Per configurare anche il cron esterno, su
[cron-job.org](https://cron-job.org) (o servizio equivalente):

- **URL**: 
  ```
  https://api.github.com/repos/mbmichele/feed_prefettura_mn/actions/workflows/build-feed.yml/dispatches
  ```
- **Metodo**: `POST`
- **Header**:
  ```
  Authorization: Bearer <IL_TUO_PAT>
  Accept: application/vnd.github+json
  Content-Type: application/json
  ```
- **Body**:
  ```json
  {"ref": "main"}
  ```
- **Frequenza**: ogni ora (o come preferisci).

Qualunque sia l'innesco (interno o esterno), il workflow rigenera
`docs/feed.xml` e fa commit solo se il contenuto è effettivamente cambiato.

## 5. Esecuzione manuale (facoltativa)

Puoi anche lanciare la Action manualmente da GitHub: **Actions → Rigenera
feed RSS notizie Prefettura di Mantova → Run workflow**.

## 6. Esecuzione locale (per test/debug)

```bash
pip install -r requirements.txt
python scripts/generate_feed.py
```

Lo script stampa a schermo quanti link ha trovato nella pagina di elenco e
quanti nuovi comunicati ha scaricato; in caso di errore (pagina bloccata,
struttura cambiata) esce con codice diverso da zero e un messaggio
diagnostico su stderr.

## Limiti e disclaimer

- Questo è un progetto amatoriale, senza scopo di lucro, non affiliato alla
  Prefettura di Mantova né al Ministero dell'Interno.
- Il feed dipende dalla struttura pubblica del sito sorgente: eventuali
  modifiche al sito possono richiedere aggiornamenti allo script.
- Il feed mantiene al massimo gli ultimi 60 comunicati (vedi `MAX_ITEMS` in
  `scripts/generate_feed.py`).

## Prompt originale (per rigenerare il pacchetto in futuro)

Il pacchetto è stato generato a partire da questo prompt:

```
Voglio un repository GitHub che generi un feed RSS pubblico non ufficiale
a partire dagli elementi pubblicati alla pagina:
https://prefettura.interno.gov.it/it/prefetture/mantova/notizie

Il flusso RSS deve contenere titolo, data, descrizione e link di ogni
comunicato.

Requisiti:
- Script Python (requests + BeautifulSoup) che fa scraping della pagina,
  individua ogni comunicato tramite i link che puntano al dettaglio
  (pattern "cs_context.jsp?...id_context=..."), risale al blocco di testo
  che lo contiene ed estrae titolo, data, link e descrizione. Le etichette
  di categoria (che terminano sempre con una virgola, es. "per il
  cittadino,") vanno scartate automaticamente, indipendentemente da quante
  e quali sono.
- Genera un file docs/feed.xml (RSS 2.0 valido, con guid, pubDate in
  formato RFC 822, fuso orario Europe/Rome).
- GitHub Action con solo "workflow_dispatch" (nessuno schedule interno):
  deve essere innescabile da un cronjob esterno (es. cron-job.org) che
  chiama l'API di GitHub per lanciare il workflow ogni ora; il workflow
  rigenera il feed e fa commit/push solo se il contenuto cambia.
- docs/index.html minimale con link al feed, per la pubblicazione tramite
  GitHub Pages (branch main, cartella /docs).
- README con istruzioni di setup (creazione repo, GitHub Pages, PAT e
  configurazione del cronjob esterno) e con questo stesso prompt incluso,
  per poter rigenerare il pacchetto in futuro.
- Consegna il tutto come pacchetto .zip scaricabile, con un numero di
  versione nel nome del file.
```

**Nota per una rigenerazione futura**: il pattern `cs_context.jsp?...
id_context=...` indicato nel prompt originale non corrisponde al sito
`prefettura.interno.gov.it` (che usa URL puliti del tipo
`/it/prefetture/mantova/notizie/<slug>`) — quel pattern appartiene invece al
sito `provincia.mantova.it`. Nella generazione di questo pacchetto lo
scraper è stato adattato di conseguenza; se rigeneri il pacchetto, verifica
prima quale sia il sito e lo schema URL realmente corretti.

### Modifiche successive al prompt originale

- **v1.1.0**: aggiunta come seconda fonte la pagina
  `https://prefettura.interno.gov.it/it/prefetture/mantova/evidenza/comunicati-stampa`.
  Lo script ora scarica entrambe le pagine di elenco (`LISTING_URLS` in
  `scripts/generate_feed.py`) e deduplica i comunicati per slug finale
  dell'URL (non per URL esatto), perché lo stesso comunicato può comparire
  sotto entrambi i prefissi `/notizie/<slug>` e
  `/comunicati-stampa/<slug>`.
- **v1.2.0**: il workflow ora ha **sia** uno schedule interno di GitHub
  Actions (ogni ora) **sia** il trigger `workflow_dispatch` per il cron
  esterno — non più solo quest'ultimo.
- **v1.3.0**: corretto l'indirizzo pubblico del feed:
  `https://mbmichele.github.io/feed_prefettura_mn/docs/feed.xml` (GitHub
  Pages pubblica dalla root del branch `main`, non dalla cartella `/docs`
  come sorgente — per questo il path include `docs/`).
- **v1.4.0**: risolto il blocco 403 osservato nella prima esecuzione reale
  della Action (log: `Status 403` su entrambe le pagine di elenco). Lo
  scraping ora usa una sessione persistente con header completi da
  browser, warm-up sulla home, `Referer` e ritentativi con backoff su
  403/429/503.
