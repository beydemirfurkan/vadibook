# vadibook pipeline

Kurtlar Vadisi bölümlerini (resmi YouTube yüklemeleri) konuşmacı etiketli, kelime zamanlı
utterance'lara çevirir. Çıktılar `data/private/` altındadır ve **asla** repoya/siteye çıkmaz.

## Kurulum (Windows, RTX GPU)

```powershell
cd pipeline
uv python install 3.12
uv sync --group dev
copy .env.example .env   # HF_TOKEN doldur (pyannote model koşullarını kabul et)
$env:PYTHONUTF8 = "1"    # Türkçe konsol çıktısı için
uv run python -c "import torch; print(torch.cuda.is_available())"   # True olmalı
```

## Kullanım

```powershell
uv run vadibook catalog                      # playlist → data/public/episodes.json (+ eksik raporu)
uv run vadibook run --ep pusu/1              # tek bölüm: fetch → asr → diarize → align
uv run vadibook run --series pusu            # bir seri; kesilirse tekrar çalıştır, kaldığı yerden devam eder
uv run vadibook asr --ep pusu/1 --model large-v3-turbo --force
uv run vadibook status
uv run pytest
```

Aşama dosyaları: `audio/{key}.p{n}.opus` → `asr/{key}.p{n}.json` → `diar/{key}.p{n}.json` →
`utterances/{key}.jsonl`; ilerleme `state/{key}.json`. `key` = `pusu-017` gibi.

## Kaynaklar

Yalnızca doğrulanmış Pana Film kanalları: `@KurtlarVadisiOfficial` (KV 1-55 playlist'i) ve
`@KurtlarVadisi` (KV 57-97 ve Pusu 1-300 playlist'leri). Playlist'lerde olmayan ama kanallarda
bulunan bölümler (`kv/56`, `pusu/86`) `data/public/catalog_extra.json` ile elle eklenir:

```json
[{"series": "pusu", "no": 86, "parts": [{"yt_id": "v755o4LBr3U", "title": "Kurtlar Vadisi Pusu 86. Bölüm"}]}]
```

## Sorun giderme

- `Could not load library cudnn_ops64_9.dll` / cuBLAS hatası: `asr.py` torch'u önce import eder; hâlâ hata
  varsa `uv add nvidia-cudnn-cu12 nvidia-cublas-cu12` ve `os.add_dll_directory(<site-packages>/nvidia/cudnn/bin)`.
- pyannote `torchcodec` import hatası: `diarize.py` sesi ffmpeg ile çözüp bellekten verir, torchcodec kullanılmaz;
  import yine kırılıyorsa `uv add "pyannote-audio==3.3.2"` + `MODEL="pyannote/speaker-diarization-3.1"` (embedding'siz).
- YouTube 429 / throttling: `--sleep 15`, gerekirse `cookies`.
