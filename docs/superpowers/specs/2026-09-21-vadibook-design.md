# vadibook — Kurtlar Vadisi Aranabilir Bilgi Tabanı

## Context

Silivri Cumhuriyet Başsavcılığı, Kaşif Kozinoğlu soruşturması kapsamında Kurtlar Vadisi'nin 397 bölümünü (97 orijinal + 300 Pusu) bilirkişiye inceletme kararı aldı. Bu, "dizide kim, kime, ne dedi?" sorusunu kamu gündemine taşıdı. **vadibook**, aynı 397 bölümü açık kaynak bir pipeline ile transkript edip konuşmacı bazında aranabilir hâle getiren, karakter/örgüt/gerçek-dünya bağlantı grafiği çıkaran ve her sonucu resmi YouTube yüklemesinin ilgili saniyesine bağlayan bir proje. Amaç: viral olmak — "bilirkişi aylarca inceleyecek, biz 3 saniyede arattırıyoruz."

Repo `C:\Users\Furkan Beydemir\vadibook` şu an boş, git değil.

### Alınan kararlar (brainstorm)

| Karar | Seçim |
|---|---|
| Derinlik | Whisper ASR + pyannote diarization + karakter eşleme ("kim, kime, ne dedi") |
| Yayın modeli | **Snippet + YouTube derin link.** Tam metin yalnızca sunucu tarafındaki arama indeksinde; repoda ve tarayıcıda tam transkript yok |
| Kapsam | 397 bölüm (KV 1-97, Pusu 1-300). Veri modeli `series` alanı taşır; filmler sonra eklenebilir |
| Stack | Python pipeline (uv) · Next.js App Router · Meilisearch · SQLite · Docker Compose (VPS) + Cloudflare |
| Konuşmacı→karakter | Ses bankası (manuel etiket ~30-40 karakter) + Claude bağlam tahmini + topluluk düzeltmesi |

### Yerel ortam
RTX 4070 12 GB, ffmpeg, Python 3.14 (→ uv ile 3.12 pinlenecek; torch/ctranslate2 wheel'leri için), uv, node. yt-dlp yok (kurulacak).

---

## Mimari

```
YouTube (resmi yükleme)
   │ yt-dlp (yalnız ses + otomatik altyazı yedek)
   ▼
pipeline/  catalog → fetch → asr → diarize → align → identify → extract → build
   │                                                              │
   │  data/private/ (gitignored): audio, asr, diar, utterances, vadibook.sqlite
   │  data/public/  (git):        episodes, characters, entities, voicebank, overrides, graph, scenes
   ▼
Meilisearch (tam metin, sadece kırpılmış snippet döner)  ◄──  web/ Next.js (arama, karakter, bölüm, grafik, dosya sayfaları)
```

Her pipeline aşaması **bölüm başına idempotent**; `data/private/state/{ep}.json` ile hangi aşamanın bittiği tutulur, `vadibook run --stage asr --ep pusu/17` gibi tek tek veya `--all` çalışır, kesilirse kaldığı yerden devam eder.

### Repo düzeni

```
vadibook/
  README.md                 TR (+ kısa EN); yasal not, katkı rehberi, takedown iletişimi
  LICENSE                   kod: MIT · data/public: CC BY 4.0
  pipeline/                 uv projesi (Python 3.12)
    pyproject.toml
    vadibook/
      cli.py                typer: catalog|fetch|asr|diarize|align|identify|extract|build|run
      catalog.py  fetch.py  asr.py  diarize.py  align.py  identify.py  extract.py  build.py
      textnorm.py           Türkçe normalizasyon (İ/ı, ASCII katlama)
      models.py             pydantic şemaları (Utterance, Scene, Relation, ...)
      prompts/              identify.md, extract.md (Claude sistem promptları)
    tests/
    tools/label_voices.py   ses bankası etiketleme aracı (küçük yerel web UI)
  web/                      Next.js (TypeScript, App Router, Tailwind)
  data/
    public/                 episodes.json, characters.json, entities.json, voicebank/, overrides/, graph/, scenes/
    private/                .gitignore'da — audio/, asr/, diar/, utterances/, state/, vadibook.sqlite
  deploy/                   docker-compose.yml (meilisearch + web + caddy), .env.example
  docs/superpowers/specs/2026-09-21-vadibook-design.md   (bu planın spec hâli)
```

---

## Pipeline aşamaları

### 1. `catalog` — bölüm envanteri
- `yt-dlp --flat-playlist -J` ile iki resmi playlist'i çek (KV: `PLOFoevjhe1HU-FncKpm_OTiSWdTbA7nfh`, Pusu: `PLOFoevjhe1HX4HquOBEASUtK_DTfqJSMX`); başlıktan `"(Pusu )?(\d+)\. ?Bölüm"` ile numara ayrıştır.
- Çok parçalı videolar ("1. Kısım/2. Kısım") için `parts: [{yt_id, offset_sec}]` tut — derin link doğru parçaya + saniyeye gider.
- Çıktı `data/public/episodes.json`; eksik/çift bölümler için rapor yazdır, elle düzelt. 397'nin tamamının bulunduğunu doğrula.

### 2. `fetch` — ses indirme
- `yt-dlp -f bestaudio -x --audio-format opus --write-auto-subs --sub-lang tr` → `data/private/audio/{ep}.opus` (+ `.tr.vtt` yedek/karşılaştırma).
- İndirmeler arası bekleme + retry (YouTube throttling); cookies opsiyonel. Ses **asla** repoya/siteye çıkmaz.

### 3. `asr` — transkripsiyon
- `faster-whisper` `large-v3` (fp16, `BatchedInferencePipeline`), `language="tr"`, `word_timestamps=True`, `vad_filter=True`.
- Halüsinasyon filtresi: `no_speech_prob > 0.6` veya `compression_ratio > 2.4` segmentleri at (jenerik müziği/sessizlik).
- Konfigürasyonla `large-v3-turbo`'ya geçilebilir; spike'ta ikisi 3 bölümde karşılaştırılır.
- Tahmin: ~700 saat ses × (large-v3 batched ~15-25× gerçek zaman) ≈ 30-45 saat GPU. Arka planda kuyruk olarak çalışır.

### 4. `diarize` — konuşmacı ayrıştırma
- `pyannote/speaker-diarization-3.1` (HF token gerekli, gated model) → `data/private/diar/{ep}.json` (turn'ler: start, end, `SPEAKER_xx`).
- Her yerel konuşmacı için ortalama embedding çıkar (`pyannote/wespeaker-voxceleb-resnet34-LM`) → `identify` aşamasında kullanılacak.
- WhisperX yerine faster-whisper + pyannote doğrudan; bağımlılık kırılganlığından kaçınmak için hizalama kendi kodumuzda (~100 satır). WhisperX yedek seçenek.

### 5. `align` — birleştirme
- Kelime bazında en çok örtüşen konuşmacıyı ata; konuşmacı değişiminde segmenti böl; aynı konuşmacının ardışık segmentlerini ≤30 sn'lik utterance'lara birleştir.
- Çıktı `data/private/utterances/{ep}.jsonl`: `{ep, idx, start, end, speaker_local, text, text_norm, words[]}`.
- Bu aşama saf fonksiyon → sentetik veriyle unit test.

### 6. `identify` — konuşmacı → karakter
1. **Sözlük:** Vikipedi/Fandom karakter listelerinden bir kez kazınıp elle gözden geçirilmiş `data/public/characters.json` (`id, name, aliases[], actor, first_ep, last_ep, org`).
2. **Ses bankası:** `tools/label_voices.py` yerel bir sayfa açar; seçili bölümlerin yerel konuşmacılarından 10-15 sn klip çalar, kullanıcı karakter adı yazar. Embedding'ler `data/public/voicebank/{character}.npy` (küçük, git'e girer). Aktör/ses yıllar içinde değişir → her dönemden örnek al.
3. **Otomatik eşleme:** bölümdeki her yerel konuşmacının embedding'i ↔ banka centroid'leri, cosine > eşik (başta 0.6, etiketli bölümlerde ölçülüp ayarlanır) → `character_id`, `source=voicebank`.
4. **LLM tahmini:** eşleşmeyen konuşmacılar için Claude'a bölümün utterance'ları (geçici etiketlerle) + o bölüm aralığında aktif karakterler verilir; hitap/bağlamdan (`"Memati, gel"` → sonraki konuşmacı Memati) atama ister. Yapısal çıktı (`output_config.format`), `confidence` alanı; yalnız `high` uygulanır, `source=llm`.
5. **Override:** `data/public/overrides/{ep}.json` — sitedeki "Bu konuşmacı yanlış mı?" butonu ön-doldurulmuş GitHub issue açar; maintainer merge eder. Override her şeyi ezer.

### 7. `extract` — bilgi grafiği
- Sahne bölme: konuşma boşluğu > 8 sn veya Claude sahne sınırı.
- Sahne başına Claude (yapısal çıktı) çıkarır:
  - `mentions`: metindeki varlık referansları → `characters.json` / `entities.json` (tip: `org | real_person | real_event | place`) kanonik id'leri; yeni adaylar ayrı listede, elle onaylanır.
  - `relations`: `(src, predicate, dst, evidence_utterance_ids, evidence_quote ≤200 karakter, confidence)`; sabit predicate sözlüğü: `ally_of, enemy_of, works_for, orders, threatens, kills, meets, family_of, loves, betrays, mentions`.
  - `summary`: 1-2 cümlelik **kendi yazdığımız** sahne özeti (diyalog kopyası değil).
- Ayrıca LLM'siz: sahne içi konuşma sırası → `conversations(a, b, turns)` "kim kiminle konuştu" kenarları.
- **Model & maliyet:** Varsayılan `claude-opus-5`, **Message Batches** (%50 indirim), karakter sözlüğü sistem promptunda `cache_control` ile önbellekli. Kaba tahmin: ~20M giriş + ~4M çıkış token → Opus 5 batch ≈ $100; Sonnet 5 batch ≈ $40 (kullanıcı seçer). Önce 3 bölümde `count_tokens` ile ölçülür.
- Python tarafı `anthropic` SDK; uygulama sırasında claude-api skill'inin `python/claude-api/README.md` + `batches.md` dosyaları okunur (SDK şekli oradan, hafızadan değil).

### 8. `build` — SQLite + dışa aktarım
- `data/private/vadibook.sqlite` tablolar: `episodes, characters, entities, speakers, utterances(text, text_norm, text_ascii), scenes, mentions, relations, conversations`.
- **Meilisearch** dokümanı: `{id, series, ep, start, end, character_id, character_name, text, text_norm, text_ascii, yt_url}`; indeks ayarı `attributesToRetrieve` `text*` hariç, `attributesToCrop: ["text:25"]` → API yalnız kırpılmış `_formatted.text` döner. Türkçe İ/ı sorunu ve şapkasız yazım için `textnorm.py` ile `text_norm` (İ→i, I→ı) ve `text_ascii` (ş→s, ğ→g…) alanları aranabilir.
- Public export (`data/public/graph/edges.json`, `scenes/{ep}.json`, `characters.json`) → site build-time'da okur. `utterances.text` **hiçbir public export'a girmez**.

---

## Web (Next.js)

| Rota | İçerik |
|---|---|
| `/` | Büyük arama kutusu; öne çıkan "dosya"lar; sayaçlar (397 bölüm, N saat, N konuşma) |
| `/ara?q=&series=&ep=&karakter=` | Sonuç kartı: snippet (vurgulu) · karakter · bölüm · `mm:ss` · **"YouTube'da o anı izle"** (`youtu.be/{id}?t={sec}`) · "Paylaş" (alıntı kartı) · "Konuşmacı yanlış mı?" |
| `/bolum/[series]/[no]` | Meta, resmi YouTube embed, sahne listesi + özetler, bölümdeki karakterler, konuşmacı zaman çizelgesi. Tam transkript **yok** |
| `/karakter/[slug]` | Bio (kendi metnimiz), göründüğü bölümler, en çok konuştuğu kişiler, ilişki kenarları (kanıt linkli), bahsettiği gerçek-dünya varlıkları |
| `/grafik` | sigma.js + graphology kuvvet grafiği (karakter/örgüt); kenara tıkla → kanıt alıntıları + linkler; bölüm aralığı slider'ı |
| `/gercek-dunya` | Gerçek kişi/olay referans indeksi → hangi bölüm, kim söyledi |
| `/dosya/[slug]` | Editoryal MDX "soruşturma dosyaları"; ilki **Kozinoğlu / Kaşifoğlu** — viral içerik |
| `/api/search` | Meilisearch'e sunucu tarafı proxy (search-only key), rate limit, Cloudflare cache; **sadece crop döner** |
| `/api/og` | Alıntı kartı görseli (≤200 karakter alıntı + karakter + bölüm + link) — paylaşım motoru |

Global: "Bu site bir kurgu eserin diyaloglarını indeksler; gerçek kişilere dair ifadeler dizi karakterlerine aittir" uyarı bandı (iftira riskine karşı). robots: `/api` hariç açık.

## Deploy
`deploy/docker-compose.yml`: `meilisearch` (master key env, search key web'e), `web` (next standalone), `caddy` (TLS). Önünde Cloudflare proxy; `/api/search` GET için cache kuralı. İndeks yerelde build edilip `meilisearch dump` olarak sunucuya taşınır (VPS'te GPU/LLM çalışmaz).

---

## Fazlar

**Faz 0 — Spike (1 gün).** `git init`, uv proje, yt-dlp; **1 bölüm** uçtan uca: fetch→asr→diarize→align. Ölç: gerçek-zaman çarpanı, Türkçe kalite (5 dk elle kontrol), large-v3 vs turbo, VRAM. YouTube otomatik altyazısının var olup olmadığını doğrula (yedek kaynak). Sonuçlara göre §3-5 parametreleri sabitlenir.
**Faz 1 — Ham veri.** `catalog` (397 doğrulanır) → `fetch` arka planda (gün sürer) → `asr`+`diarize`+`align` kuyruğu. Bu faz bittiğinde konuşmacılar hâlâ `SPEAKER_xx`.
**Faz 2 — Arama MVP (erken yayın).** `build` + Meilisearch + `/`, `/ara`, `/bolum` sayfaları, konuşmacı "—" gösterilir. Deploy. **Bu noktada viral dalga yakalanabilir**; gerisi aşamalı iyileşir.
**Faz 3 — Kimlik.** `characters.json` tohumlama, `label_voices.py`, ses bankası etiketleme (kullanıcı, ~1-2 saat), `identify` (banka + LLM), override akışı + "yanlış mı?" butonu.
**Faz 4 — Grafik.** `extract` 10 bölümde prompt/şema ayarı → tam batch → `/karakter`, `/grafik`, `/gercek-dunya`, alıntı kartları.
**Faz 5 — Lansman.** İlk `/dosya/kozinoglu-kasifoglu`, README/CONTRIBUTING, issue şablonları, sosyal paylaşım.

Onay sonrası ilk iş: `git init` → todox `get_context(repo_root)` ile proje kaydı → faz başına `create_task`; bu plan `docs/superpowers/specs/` altına spec olarak kopyalanır.

---

## Riskler ve korkuluklar
- **Telif:** tam transkript dışa aktaran hiçbir endpoint yok; crop ≤ ~25 kelime; kanıt alıntıları ≤ 200 karakter; ses dağıtılmaz; README'de takedown iletişimi. Yalnız resmi Pana Film yüklemelerine link verilir (onlara izlenme taşır).
- **YouTube ToS:** yt-dlp ile indirme araştırma pratiği ama ToS'a aykırı; audio yalnız yerel işleme için, kullanıcıya açıkça belirtilir.
- **İftira:** kurgu uyarısı her sayfada; gerçek kişi sayfaları "dizide şöyle geçiyor" çerçevesinde, olgu iddiası yok.
- **Kalite:** Whisper Türkçe'de özel isimleri bozar (Kaşifoğlu→"Kâşif oğlu"); `characters.json` alias'ları + `initial_prompt` ile karakter adları verilerek ASR iyileştirilir; arama `text_ascii` ile toleranslı.
- **Python 3.14:** ML wheel'leri yok → uv ile 3.12.
- **Diarization eşiği** ve **LLM güveni** etiketli 3 bölümde ölçülmeden tam çalıştırma yapılmaz.

## Doğrulama
- Unit: `align` (örtüşme/birleştirme), `textnorm` (İstanbul/ısı/şapkasız), `catalog` başlık ayrıştırma; pytest.
- Kalite: 3 bölüm × 5 dk elle transkript kontrolü (kelime hata oranı kabaca), konuşmacı doğruluğu etiketli bölümlerde ≥ %85 hedef.
- Uçtan uca: `vadibook run --ep pusu/1 --all` → `docker compose up` → `http://localhost:3000/ara?q=Kaşifoğlu` snippet döner, tam metin response'ta yok (network sekmesinde doğrula), link YouTube'da doğru saniyeye gider.
- Grafik: `/grafik`'te Polat–Memati kenarına tıklayınca kanıt alıntıları linkleriyle açılır.
- Performans: `/api/search` p95 < 200 ms yerelde; Cloudflare cache HIT tekrar sorguda.
