# ytstudio analytics - Power Tool Plan

## Visie

De analytics module wordt de reden waarom creators en marketeers ytstudio installeren.
YouTube Studio geeft dashboards, maar geen CLI. Geen pipelines. Geen automatisering.
Wij geven ze de data als bouwstenen: gestructureerd, filterbaar, composable.

AI agents (zoals Gozert) worden first-class users: JSON output, consistente schemas,
exit codes, en queries die direct beantwoorden wat een agent wil weten.

---

## Ontwerpprincipes

1. **Elke query = 1 API call.** Geen magie, geen verborgen aggregaties. Power users
   willen weten wat ze krijgen.

2. **Dimensies en metrics zijn first-class.** Niet hardcoded per commando, maar als
   parameters. `ytstudio analytics query --metrics views,likes --dimensions day` is
   krachtiger dan 20 subcommands.

3. **Output is altijd machine-readable.** `-o json` voor alles. `-o csv` voor
   spreadsheet-mensen. Tabellen zijn de default voor humans.

4. **Vergelijking is ingebouwd.** Periodes vergelijken, videos vergelijken, benchmarks
   berekenen. Dat is wat Studio niet doet in bulk.

5. **Alerts zijn passief.** Geen daemon, geen webhook server. Output een exit code of
   een JSON verdict dat een cron job / AI agent kan consumeren.

---

## Architectuur

### Tier 1: Raw Query Engine (de basis)

```
ytstudio analytics query \
  --metrics views,likes,shares,estimatedMinutesWatched \
  --dimensions day \
  --filter video==VIDEO_ID \
  --filter country==NL \
  --start 2026-01-01 --end 2026-02-01 \
  --sort -views \
  --limit 50 \
  -o json
```

Een directe vertaling van de YouTube Analytics API `reports.query` endpoint.
Alle metrics en dimensies die de API ondersteunt, geen kunstmatige beperkingen.

Dit is het fundament. Alle andere commands zijn convenience wrappers hieromheen.

**Ondersteunde metrics** (volledige set uit de API):

Groep | Metrics
--- | ---
Views | views, engagedViews, redViews, viewerPercentage
Reach | videoThumbnailImpressions, videoThumbnailImpressionsClickRate
Watch time | estimatedMinutesWatched, estimatedRedMinutesWatched, averageViewDuration, averageViewPercentage
Engagement | likes, dislikes, comments, shares, subscribersGained, subscribersLost, videosAddedToPlaylists, videosRemovedFromPlaylists
Cards | cardImpressions, cardClicks, cardClickRate, cardTeaserImpressions, cardTeaserClicks, cardTeaserClickRate
Annotations | annotationImpressions, annotationClicks, annotationClickThroughRate, annotationCloses, annotationCloseRate
Revenue* | estimatedRevenue, estimatedAdRevenue, grossRevenue, estimatedRedPartnerRevenue, monetizedPlaybacks, playbackBasedCpm, adImpressions, cpm
Playlist | playlistViews, playlistStarts, viewsPerPlaylistStart, averageTimeInPlaylist, playlistSaves, playlistEstimatedMinutesWatched

*Revenue vereist yt-analytics-monetary.readonly scope

**Ondersteunde dimensies:**

Groep | Dimensies
--- | ---
Tijd | day, month
Geo | country, province, city, continent, subContinent, dma
Content | video, playlist, group, creatorContentType
Traffic | insightTrafficSourceType, insightTrafficSourceDetail
Playback | playbackLocationType, liveOrOnDemand
Device | deviceType, operatingSystem
Audience | ageGroup, gender, subscribedStatus, youtubeProduct
Sharing | sharingService
Ads | adType

### Tier 2: Smart Commands (convenience)

Wrappers rond de query engine die veelgevraagde analyses pakken.

#### `analytics overview` (bestaand, uitbreiden)

Toevoegen:
- `--compare` flag: vergelijk met vorige periode (delta's + %)
- Thumbnail impressions + CTR
- Shares
- Net subscribers (gained - lost)

```
ytstudio analytics overview --days 28 --compare

Channel Analytics (last 28 days vs previous 28 days)

  views           45.2K    +12.3%  ▲
  watch time      892h     -3.1%   ▼
  avg duration    3:42     +0:15
  impressions     312K     +8.7%   ▲
  CTR             4.2%     +0.3pp
  subscribers     +342     net (+401 / -59)
  likes           1.8K     +22.1%  ▲
  shares          234      +45.0%  ▲
  comments        89       -5.3%   ▼
```

#### `analytics video` (bestaand, uitbreiden)

Toevoegen:
- Impressions + CTR
- Subscriber impact (gained/lost from this video)
- `--compare` met kanaalgemiddelde
- `--daily` flag voor dagelijkse breakdown

#### `analytics audience`  (nieuw)

```
ytstudio analytics audience [VIDEO_ID] --days 28 -o json

{
  "demographics": {
    "age_groups": [
      {"group": "25-34", "percentage": 34.2},
      {"group": "35-44", "percentage": 28.1}, ...
    ],
    "gender": [
      {"gender": "male", "percentage": 72.1},
      {"gender": "female", "percentage": 27.9}
    ]
  },
  "subscription_status": {
    "subscribed": {"views": 12400, "percentage": 27.4},
    "not_subscribed": {"views": 32800, "percentage": 72.6}
  },
  "devices": [
    {"type": "MOBILE", "views": 28100, "percentage": 62.2},
    {"type": "DESKTOP", "views": 12300, "percentage": 27.2},
    {"type": "TV", "views": 3200, "percentage": 7.1}, ...
  ],
  "geography": {
    "top_countries": [
      {"country": "NL", "views": 38200, "percentage": 84.5},
      {"country": "BE", "views": 4100, "percentage": 9.1}, ...
    ]
  }
}
```

Wie kijkt er? Essentieel voor sponsordeals, content strategie, en het begrijpen
van je publiek.

#### `analytics reach` (nieuw)

```
ytstudio analytics reach [VIDEO_ID] --days 28

Reach Funnel (last 28 days)

  impressions     312.4K
  ├─ CTR          4.2%
  ├─ views        13.1K
  ├─ engaged      11.8K   (90.1% van views)
  ├─ avg viewed   62.3%
  └─ subscribers  +48     from this video

Traffic Sources:
  YouTube search       5.2K   39.7%   (top: "luckytv", "sander van de pavert")
  Suggested videos     3.8K   29.0%
  Browse features      2.1K   16.0%
  External             1.2K    9.2%   (top: reddit.com, twitter.com)
  Channel pages        0.8K    6.1%
```

De complete "funnel": van impressie tot subscriber. Plus traffic source details
(welke zoektermen, welke externe sites). Dit is wat creators het meest missen
in geautomatiseerde tooling.

#### `analytics trends` (nieuw)

```
ytstudio analytics trends --days 90 --metrics views,subscribersGained --interval day -o json

[
  {"date": "2026-01-15", "views": 1234, "subscribersGained": 12},
  {"date": "2026-01-16", "views": 45678, "subscribersGained": 342},
  ...
]
```

Tijdreeksen. De basis voor grafieken, anomaly detection, en growth tracking.
Met `--interval day|month` en vrije metrics keuze.

#### `analytics compare` (nieuw)

```
ytstudio analytics compare VIDEO_ID1 VIDEO_ID2 [VIDEO_ID3...] --days 28

Comparing 3 videos (last 28 days)

                          De Coalitie    Koningsdag     Formatie
  views                   125.4K         89.2K          45.1K
  avg view %              68.2%          54.1%          71.3%
  CTR                     5.1%           3.8%           6.2%
  likes                   4.2K           2.1K           1.8K
  comments                342            128            89
  subscribers gained      +234           +89            +156
```

Side-by-side vergelijking. Essentieel om te leren welke content werkt en waarom.

#### `analytics benchmark` (nieuw)

```
ytstudio analytics benchmark VIDEO_ID --days 28

Performance vs Channel Average (last 28 days, 45 videos)

  views            125.4K      +340%  from avg (28.4K)    ████████████████ top 2%
  CTR              5.1%        +1.2pp from avg (3.9%)     ████████████░░░░ top 15%
  avg view %       68.2%       +12.1pp from avg (56.1%)   ██████████████░░ top 8%
  likes/view       3.4%        +0.8pp from avg (2.6%)     █████████████░░░ top 11%
  comments/view    0.27%       +0.12pp from avg (0.15%)   ██████████████░░ top 7%
```

Hoe presteert een video ten opzichte van het kanaalgemiddelde?
Dit is wat marketeers handmatig in spreadsheets doen.

### Tier 3: AI Agent Features

#### `analytics check` (nieuw)

Een "health check" die een AI agent periodiek kan draaien.
Output is een gestructureerd verdict, geen proza.

```
ytstudio analytics check --days 7 -o json

{
  "status": "attention",
  "period": {"start": "2026-01-30", "end": "2026-02-06", "days": 7},
  "alerts": [
    {
      "type": "viral_candidate",
      "severity": "info",
      "video_id": "abc123",
      "title": "De Coalitie: Echt Al Lekker Op Weg",
      "detail": "Views 340% above channel average (125K vs 28K avg)",
      "metrics": {"views": 125400, "channel_avg": 28400}
    },
    {
      "type": "engagement_drop",
      "severity": "warning",
      "detail": "Channel engagement rate dropped 15% vs previous 7 days",
      "metrics": {"current": 3.2, "previous": 3.8, "delta_pct": -15.8}
    },
    {
      "type": "subscriber_spike",
      "severity": "info",
      "detail": "+342 subscribers (3.2x normal weekly rate)",
      "metrics": {"gained": 342, "weekly_avg": 107}
    }
  ],
  "summary": {
    "views": 45200,
    "views_delta_pct": 12.3,
    "subscribers_net": 342,
    "top_video": {"id": "abc123", "title": "De Coalitie...", "views": 125400}
  }
}
```

Exit codes:
- 0: alles normaal
- 1: attention (er is iets opvallends)
- 2: warning (er is iets dat actie vereist)

Zo kan een cron job of Gozert direct beslissen of er iets te melden is zonder
de JSON te parsen.

#### `analytics digest` (nieuw)

```
ytstudio analytics digest --days 7 --days 28 --days 90 -o json
```

Geeft een compact overzicht over meerdere periodes. Perfect voor een wekelijkse
samenvatting die een agent naar Telegram stuurt.

```json
{
  "channel": "LuckyTV_official",
  "generated_at": "2026-02-06T19:00:00Z",
  "periods": {
    "7d": {"views": 45200, "watch_hours": 892, "subs_net": 342, ...},
    "28d": {"views": 180400, "watch_hours": 3200, "subs_net": 1204, ...},
    "90d": {"views": 520100, "watch_hours": 9800, "subs_net": 3420, ...}
  },
  "trends": {
    "views_7d_vs_28d_avg": "+12.3%",
    "subs_7d_vs_28d_avg": "+34.1%"
  },
  "top_videos_7d": [
    {"id": "abc123", "title": "...", "views": 125400}
  ]
}
```

---

## Implementatieplan

### Fase 1: Foundation (8-12 uur)

1. **Query engine** (`analytics query`)
   - Directe wrapper om reports.query
   - Alle metrics/dimensies als parameters
   - Output: table, json, csv
   - Dit is de motor onder alles

2. **Uitbreiding overview**
   - Impressions + CTR toevoegen
   - `--compare` flag (vs vorige periode)
   - Shares, net subscribers

3. **Uitbreiding video**
   - Impressions + CTR per video
   - `--daily` flag

### Fase 2: Audience & Reach (6-8 uur)

4. **analytics audience** - demografie, devices, geo, sub status
5. **analytics reach** - funnel + traffic source details
6. **analytics trends** - tijdreeksen met vrije metrics

### Fase 3: Comparison & Intelligence (6-8 uur)

7. **analytics compare** - multi-video vergelijking
8. **analytics benchmark** - video vs kanaalgemiddelde
9. **analytics check** - automated health check met exit codes

### Fase 4: Agent Integration (4-6 uur)

10. **analytics digest** - multi-period compact overzicht
11. **CSV output** voor alle commands (`-o csv`)
12. **Consistent JSON schemas** documenteren (zodat agents weten wat ze krijgen)

### Totaal: ~24-34 uur

---

## Technische keuzes

- **Geen caching.** De API is snel genoeg en data verandert. Keep it simple.
- **Geen rate limiting.** YouTube Analytics API heeft een ruim quotum (200 queries/dag
  voor reports.query). Documenteer het limiet, laat de user managen.
- **Revenue opt-in.** Revenue metrics alleen als de OAuth scope het toelaat. Graceful
  fallback als de scope er niet is.
- **Backward compatible.** Bestaande commands behouden hun interface. Nieuwe features
  zijn additive (nieuwe flags, nieuwe subcommands).

---

## Wat dit oplevert voor LuckyTV

1. Gozert kan `analytics check` in een cron draaien en alleen melden als er iets is
2. Wekelijkse digest naar Telegram zonder handmatig Studio openen
3. Vergelijken welke video stijl het beste werkt (compare + benchmark)
4. Traffic source analyse: welke zoektermen brengen kijkers (reach)
5. Audience data voor sponsorgesprekken (audience)
6. Shorts vs long-form performance splitsen (query met creatorContentType)

## Wat dit oplevert voor andere users

1. Marketeers: geautomatiseerde rapportages, CSV exports voor Excel
2. Agencies: multi-video vergelijkingen, benchmarks voor klanten
3. Developers: JSON output, composable met jq/scripts
4. AI agents: health checks met exit codes, gestructureerde digests
