# vadibook

**Kurtlar Vadisi'nin 397 bölümündeki her konuşmayı arayın; resmi YouTube yüklemesinde tam o saniyeye gidin.**

Kurtlar Vadisi (97 bölüm) ve Kurtlar Vadisi Pusu (300 bölüm), Pana Film'in resmi YouTube kanallarından
alınan sesle yerel makinede transkript edilir (faster-whisper), konuşmacılara ayrılır (sherpa-onnx +
pyannote segmentation), kelime zamanlı hâle getirilir ve aranabilir bir arşiv olarak sunulur. Amaç:
"dizide kim, kime, ne zaman, ne dedi?" sorusuna saniyeler içinde cevap vermek.

> Eylül 2026'da Silivri Cumhuriyet Başsavcılığı, bir soruşturma kapsamında dizinin 397 bölümünü bilirkişiye
> inceletme kararı aldı. Bilirkişi aylarca inceleyecek; bu proje aynı 397 bölümü herkes için aranabilir yapar.

## Nasıl çalışır

```
resmi YouTube yüklemeleri
   │ yt-dlp (yalnız ses)
   ▼
pipeline/   catalog → fetch → asr → diarize → align → build
   │            data/private/  (gitignored: ses, transkript, sqlite — asla yayımlanmaz)
   │            data/public/   (episodes.json, karakter sözlüğü, ses bankası etiketleri)
   ▼
Meilisearch (tam metin, sunucu içi)  ◄──  web/ Next.js  →  /ara  /bolum/pusu/17
```

- **Site tam transkript yayımlamaz.** Arama sonuçları ≤25 kelimelik kırpılmış alıntı + resmi YouTube
  yüklemesine zaman damgalı derin link (`youtu.be/{id}?t={saniye}`) döner. `/api/search` tam metin alanını
  hiç geri vermez; Meilisearch dış dünyaya kapalıdır.
- Ses ve video barındırılmaz; bölüm sayfaları resmi embed'i gösterir.
- Konuşmacı etiketleri otomatiktir ve hata içerebilir; karakter isimleri (Faz 3) topluluk düzeltmesiyle
  iyileşir.

## Yasal not

Bu proje bir **kurgu eserin** diyaloglarını indeksler. Gerçek kişilere dair ifadeler dizi karakterlerine
aittir; bu site hiçbir gerçek kişi hakkında olgu iddiasında bulunmaz. Dizi Pana Film'in eseridir; burada
yalnızca resmi yüklemelere bağlantı verilir, metinlerin tamamı yayımlanmaz. Hak sahibiyseniz ve bir
içeriğin kaldırılmasını istiyorsanız GitHub üzerinden issue açmanız yeterlidir.

## Yerelde çalıştırma

```powershell
# 1) pipeline (Python 3.12, uv, ffmpeg, NVIDIA GPU önerilir)
cd pipeline
uv sync --group dev
uv run vadibook catalog                 # playlist → data/public/episodes.json
uv run vadibook run --ep pusu/1         # fetch → asr → diarize → align (tek bölüm)
uv run vadibook status

# 2) arama motoru
cp deploy/.env.example deploy/.env      # MEILI_MASTER_KEY üret
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d
uv run vadibook build --push --meili-key $env:MEILI_MASTER_KEY

# 3) site
cd web
cp .env.example .env.local              # MEILI_SEARCH_KEY: deploy/README.md
pnpm install && pnpm dev
```

Ayrıntı: [`pipeline/README.md`](pipeline/README.md), [`deploy/README.md`](deploy/README.md).
Tasarım kararları: [`docs/superpowers/specs/`](docs/superpowers/specs/), ölçümler:
[`docs/superpowers/notes/`](docs/superpowers/notes/).

## Durum

- [x] Faz 0 — spike: ASR/diarization parametreleri ölçüldü
- [x] Faz 1 — 397 bölüm kataloglandı; ses + transkript üretimi arka planda
- [x] Faz 2 — arama MVP (Next.js + Meilisearch)
- [ ] Faz 3 — konuşmacı → karakter eşleme (ses bankası + LLM + topluluk)
- [ ] Faz 4 — karakter/örgüt ilişki grafiği
- [ ] Faz 5 — lansman

Bilinen sorun: 2003-05 dönemi (Kurtlar Vadisi) yüklemelerinde diarization aşırı birleştiriyor; Pusu
tarafı sağlıklı. Bkz. `docs/superpowers/notes/`.

## Katkı

Issue ve PR'lara açık. Konuşmacı etiketi düzeltmeleri `data/public/overrides/` üzerinden gelecek (Faz 3).

## Lisans

Kod: [MIT](LICENSE). `data/public/` altındaki türetilmiş yapısal veri: CC BY 4.0. Ses, video ve
transkript metinleri bu repoda yer almaz ve dağıtılmaz.
