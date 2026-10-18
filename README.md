# Feed RSS non ufficiale — Notizie e comunicati stampa Prefettura di Mantova

Genera un feed RSS 2.0 non ufficiale a partire da due pagine pubbliche del
sito della Prefettura di Mantova:

- https://prefettura.interno.gov.it/it/prefetture/mantova/notizie
- https://prefettura.interno.gov.it/it/prefetture/mantova/comunicazioni

Le pagine di dettaglio sono state osservate sotto due prefissi diversi
(`.../notizie/<slug>`, `.../comunicazioni/<slug>` e, per i comunicati
storici, `.../comunicati-stampa/<slug>`); lo stesso
comunicato può comparire con lo stesso slug sotto entrambi i prefissi
(alias interni del sito), quindi lo script deduplica per slug e non per URL
esatto, per evitare doppioni nel feed.

## 📡 Indirizzo del feed RSS

```
https://mbmichele.github.io/feed_prefettura_mn/docs/feed.xml
```

Questo è l'indirizzo da incollare in qualunque lettore RSS (Feedly,
NetNewsWire, Thunderbird, ecc.). È raggiungibile dopo aver completato i
passi 1–2 qui sotto (repository + GitHub Pages attivi) e dopo la prima
esecuzione riuscita del workflow. Il feed è attivo e si aggiorna
regolarmente — vedi comunque la sezione sotto sul blocco anti-bot
occasionale del sito sorgente, già gestito automaticamente dal workflow.

Il repository di riferimento è:
[https://github.com/mbmichele/feed_prefettura_mn](https://github.com/mbmichele/feed_prefettura_mn)

## ℹ️ Stato attuale: blocco anti-bot occasionale, già gestito

Durante lo sviluppo, tre esecuzioni reali del workflow (19 settembre, 3
ottobre e 10 ottobre 2026) avevano ricevuto **403** dal sito su entrambe
le pagine, anche con un browser reale (Playwright + Chromium headless),
facendo pensare a un blocco sugli indirizzi IP dei runner GitHub-hosted
(datacenter cloud).

**Monitoraggio successivo (controllo del 16/10/2026):** su un campione
delle ultime 100 esecuzioni del workflow, **99 sono andate a buon fine** e
il feed si aggiorna regolarmente con contenuti reali. È stata trovata
**una sola esecuzione fallita** (13/10/2026), con lo stesso pattern 403
osservato in precedenza, risolta automaticamente dall'esecuzione
successiva un'ora dopo, senza alcun intervento manuale. Il blocco quindi
non è (più, o non era) sistematico, ma **occasionale/intermittente**, ed è
già gestito correttamente dal comportamento esistente dello script:
ritentativi con backoff e commit solo in caso di successo (un run fallito
non scrive mai un feed vuoto o corrotto).

Se in futuro il blocco dovesse tornare a essere sistematico, il codice
(`scripts/generate_feed.py`) resta comunque predisposto per le due vie
utili elencate sotto, entrambe disattivate di default (nessun costo,
nessun comportamento diverso finché non le attivi):

### Opzione A — Runner self-hosted (gratuita, richiede una tua macchina)

Fai girare il workflow su un tuo computer o server sempre acceso, con un
indirizzo IP residenziale/non-datacenter (es. un Raspberry Pi, un mini-PC,
o un server di casa):

1. Nel repository GitHub: **Settings → Actions → Runners → New self-hosted
   runner**, scegli il sistema operativo della tua macchina e segui le
   istruzioni per installare e registrare il runner (scarica un pacchetto,
   lo esegui con un token fornito da GitHub).
2. Lascia il runner in esecuzione come servizio (le istruzioni di GitHub
   includono un comando `run.sh` da poter installare come servizio
   systemd su Linux).
3. In `.github/workflows/build-feed.yml`, cambia:
   ```yaml
   runs-on: ubuntu-latest
   ```
   in:
   ```yaml
   runs-on: self-hosted
   ```
4. Da quel momento il workflow (sia per lo schedule interno sia per il
   cronjob esterno) gira sulla tua macchina, con il tuo IP: se il blocco è
   davvero sui range IP dei datacenter cloud, dovrebbe sparire.

Limite: la tua macchina deve restare accesa e raggiungibile per far
scattare lo schedule orario.

### Opzione B — Proxy residenziale a pagamento

Se non hai una macchina sempre accesa, puoi instradare le richieste di
Playwright attraverso un servizio di proxy residenziali (es. Bright Data,
Smartproxy, IPRoyal e simili — hanno un costo mensile o a consumo).

1. Sottoscrivi un servizio di proxy residenziali e ottieni le credenziali
   (indirizzo del proxy, utente, password).
2. Nel repository GitHub: **Settings → Secrets and variables → Actions →
   New repository secret**, crea:
   - `PROXY_SERVER` (es. `http://geo.iproyal.com:12321`)
   - `PROXY_USERNAME` (se richiesto dal servizio)
   - `PROXY_PASSWORD` (se richiesto dal servizio)
3. Non serve modificare altro: lo script (`scripts/generate_feed.py`) e il
   workflow (`build-feed.yml`) leggono già queste variabili e, se presenti,
   le passano a Playwright; se assenti, continuano a funzionare come ora
   (senza proxy, senza costi).

### Se non fai nulla

Non serve fare nulla per ora: il workflow funziona nella quasi totalità
delle esecuzioni (vedi sopra). Nei rari casi in cui un'esecuzione riceve
403, il feed resta semplicemente quello dell'ultima esecuzione riuscita —
nessun danno, perché il workflow fa commit solo quando il feed cambia e
solo in caso di successo, quindi un run fallito non sporca mai la
cronologia del repository né pubblica un feed vuoto o corrotto.

## Struttura del repository

```
.
├── scripts/
│   └── generate_feed.py       # scraping (Playwright) + generazione RSS
├── docs/
│   ├── index.html             # pagina minima per GitHub Pages (con il link copiabile)
│   └── feed.xml               # feed generato (committato dalla Action)
├── .github/workflows/
│   └── build-feed.yml         # Action con schedule interno + workflow_dispatch
├── requirements.txt
└── README.md
```

## 1. Creazione del repository

1. Crea il repository (pubblico) su GitHub con il nome
   `feed_prefettura_mn`, se non esiste già.
2. Carica tutto il contenuto di questo pacchetto nel branch `main`.

## 2. Attivazione di GitHub Pages

1. Vai su **Settings → Pages**.
2. In "Build and deployment", seleziona **Deploy from a branch**.
3. Branch: `main`, cartella: `/ (root)`.
4. Salva. Il feed sarà raggiungibile (dopo qualche minuto) su:
   ```
   https://mbmichele.github.io/feed_prefettura_mn/docs/feed.xml
   ```

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
`docs/feed.xml` e fa commit solo se il contenuto è effettivamente cambiato
— sempre che riesca a leggere il sito sorgente (vedi sezione sul blocco
anti-bot sopra).

## 5. Esecuzione manuale (facoltativa)

Puoi anche lanciare la Action manualmente da GitHub: **Actions → Rigenera
feed RSS notizie Prefettura di Mantova → Run workflow**.

## 6. Esecuzione locale (per test/debug)

```bash
pip install -r requirements.txt
playwright install chromium
python scripts/generate_feed.py
```

Eseguito dal tuo computer di casa (non da un runner cloud), questo comando
è anche il modo più rapido per verificare se il blocco è davvero legato
all'IP dei datacenter: se in locale funziona e sui runner GitHub-hosted no,
la diagnosi è confermata.

Lo script stampa a schermo quanti link ha trovato in ciascuna pagina di
elenco e quanti nuovi comunicati ha scaricato; in caso di errore (pagina
bloccata, struttura cambiata) esce con codice diverso da zero e un
messaggio diagnostico su stderr.

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
- **v1.4.0**: risolto (apparentemente) il blocco 403 osservato nella prima
  esecuzione reale della Action. Lo scraping ora usa una sessione
  persistente con header completi da browser, warm-up sulla home,
  `Referer` e ritentativi con backoff su 403/429/503. **Rivelatosi
  insufficiente** — vedi v2.0.0.
- **v1.5.0**: indirizzo del feed reso più visibile e copiabile — blocco
  codice dedicato in cima al README e campo di testo con copia-al-click in
  `docs/index.html`.
- **v2.0.0**: sostituito `requests` con **Playwright (Chromium headless)**
  per lo scraping, dopo che il blocco 403 è persistito anche con header
  completi, sessione persistente e ritentativi (visto in due esecuzioni
  reali della Action). Aggiunto lo step "Installa Chromium (Playwright)"
  al workflow e `playwright>=1.40` a `requirements.txt`; aggiunto anche un
  ritentativo con `git pull --rebase` sul push, per il caso di esecuzioni
  concorrenti fra cron interno ed esterno.
- **v2.1.0**: confermato (log del 10/10/2026) che il blocco persiste
  **anche** con Playwright/Chromium headless reale — stesso 403 di prima,
  nonostante un browser vero. Questo esclude il fingerprinting del client
  e punta a un blocco sull'IP dei runner GitHub-hosted. Aggiunto supporto
  opzionale (disattivato di default) a un proxy residenziale via i Secrets
  `PROXY_SERVER` / `PROXY_USERNAME` / `PROXY_PASSWORD`, e documentata
  l'alternativa del runner self-hosted (vedi sezione "Stato attuale" sopra).
  Nessuna ulteriore modifica allo User-Agent/header avrebbe effetto: il
  problema è di rete, non di fingerprinting.
- **v2.2.0**: controllo dello storico reale delle esecuzioni su GitHub
  (16/10/2026): su 100 run recenti, 99 riuscite e una sola fallita (poi
  autorisolta al run successivo), a conferma che il blocco IP è
  occasionale e già gestito correttamente dal meccanismo esistente di
  ritentativi + commit-solo-su-successo. Nessuna modifica al codice:
  aggiornata solo la sezione "Stato attuale" del README, che descriveva
  un blocco sistematico ormai superato dai fatti.
- **v2.3.0**: la seconda fonte non è più
  `.../evidenza/comunicati-stampa` ma
  `https://prefettura.interno.gov.it/it/prefetture/mantova/comunicazioni`.
  Le fonti attuali sono quindi `notizie` e `comunicazioni`
  (`LISTING_URLS` in `scripts/generate_feed.py`). `DETAIL_PATH_RE` ora
  riconosce anche `/comunicazioni/<slug>` (mantenendo
  `/comunicati-stampa/<slug>` per non perdere né duplicare gli elementi già
  presenti nel feed). Se i link di dettaglio della pagina `comunicazioni`
  usassero un prefisso diverso, lo script lo segnala su stderr: basta
  aggiungerlo a `DETAIL_PATH_RE`.
