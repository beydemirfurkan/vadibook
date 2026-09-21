# Faz 0 spike bulguları — pusu/1 (2026-09-21)

Bölüm: Kurtlar Vadisi Pusu 1 (`eQddhIupB3A`), 87.6 dk, RTX 4070 12 GB, faster-whisper 1.2.1, torch 2.11+cu128.

## ASR

| Ölçüm | large-v3 | large-v3-turbo |
|---|---|---|
| RTF (işlem/ses) | 0.019 (52×) | **0.010 (99×)** |
| Süre (87.6 dk ses) | 1.7 dk | 0.9 dk |
| Segment / kelime (filtre sonrası) | 102 / 4804 | 103 / **4942** |
| Kelime güveni medyan · <0.5 oranı | 0.998 · 0.9 % | 0.998 · 1.0 % |
| 40 sn+ konuşmasız boşluk | 3 | **1** |
| YouTube oto-altyazı ile token uyumu (recall / precision) | 0.881 / 0.873 | **0.903** / 0.870 |
| İki model arası dizi benzerliği | 0.963 | |
| Halüsinasyon (blocklist isabeti) | 0 | 0 |
| Özel isimler (Polat/Memati/Abdülhey) | 12/10/8 | 14/10/8 |
| batch_size 16, fp16 | sorunsuz | sorunsuz |

YouTube otomatik TR altyazısı: **var** (Pusu kanalı); KV 1-55 kanalında **yok**.

### Kapsama sorunu ve düzeltmesi

İlk çalıştırma (VAD eşiği 0.5, whisper iç eşikleri açık) YouTube'un yoğun altyazı yazdığı 5 aralıkta
(toplam ~7 dk) hiç kelime üretmedi. Dilim testleri gösterdi ki:

- Silero VAD eşiği 0.5, dizinin yüksek müziği altındaki diyaloğu konuşma saymıyor; **0.3** aynı 90 sn'lik
  dilimde 80 → 139 kelime verdi (0.2 aynı sonucu verdi, gürültü riski için 0.3 seçildi).
- Kalan "boşluklar" gerçek: müzik ağırlıklı sahneler (YouTube `[Müzik]` etiketi + tek kelimelik ünlemler).
- Whisper'ın iç `no_speech`/`logprob` düşürmesi kapatıldı; tüm segmentler ham kaydediliyor, filtre
  `align` aşamasında (`asr.filter_segments`) uygulanıyor → filtre GPU çalıştırmadan ayarlanabilir.
- Filtre kuralı whisper'ın kanonik kuralı: `no_speech_prob > 0.6 VE avg_logprob < -1.0` → sessiz;
  `compression_ratio > 2.4` → tekrar halüsinasyonu; blocklist ("Altyazı M.K." vb.).

## Karar

- **ASR modeli: `large-v3-turbo`** (varsayılan). Gerekçe: 2× hız, bağımsız referansla (YouTube) daha yüksek
  uyum, daha az boşluk, aynı güven. `--model large-v3` seçeneği duruyor.
- `VAD_OPTIONS = {threshold: 0.3, min_silence_duration_ms: 1000, speech_pad_ms: 400}`
- `batch_size` 16.
- Tahmini toplam ASR süresi (592 saat ses × RTF 0.010) ≈ **6 saat GPU**.

## Sürprizler / dead end'ler

- Batched pipeline segmentleri 30 sn konuşmayı 100-250 sn'lik zaman aralığına yayabiliyor (sessizlikleri atıp
  parçaları birleştiriyor); kelime zaman damgaları doğru, segment start/end yanıltıcı. Align kelime bazlı
  çalıştığı için sorun değil.
- YouTube cue sayısı konuşma yoğunluğu ölçüsü değil: müzik sırasında da cue üretiyor. Kelime sayısıyla
  karşılaştırmak gerekiyor.
- Bash aracı heredoc içindeki `\\n`'i gerçek satır sonuna çeviriyor; dosya yazarken Write aracı ya da `chr(92)`.

## Diarization (sherpa-onnx, token'sız)

pyannote community-1 HF'de gated (token + form) olduğu için backend **sherpa-onnx**'a çevrildi: k2-fsa'nın
dağıttığı MIT lisanslı pyannote `segmentation-3.0` ONNX'i + WeSpeaker VoxCeleb ResNet34-LM embedding (pyannote 3.1'in
kendi modeli). Tamamen yerel, CPU (16 thread), GPU'daki ASR ile paralel.

| Ölçüm | Değer |
|---|---|
| RTF (16 thread, CPU) | 0.044 (23×) — 88 dk bölüm 3.9 dk |
| Kümeleme eşiği taraması (10 dk dilim) | 0.5→18, 0.65→8, 0.75→5, 0.85→4, 0.95→1 konuşmacı |
| Seçilen eşik | **0.7** (pyannote 3.1'in bu embedding için ayarlı değeri; Faz 3 ses bankasıyla yeniden ölçülecek) |
| pusu/1 sonucu | 35 konuşmacı (11'i ≥60 sn, 14'ü <10 sn gürültü kümesi), 541 utterance, 40.8 dk konuşma |
| Embedding | 256-boyut, konuşmacı başına en uzun turn'lerden ≤60 sn ses, L2-normalize |
| 397 bölüm tahmini | 592 sa × 0.044 ≈ **26 saat CPU** |

Eşik 0.5 ile tek bölümde 109 konuşmacı çıkmıştı (aşırı bölme) — dead end.

## Bekleyen

- İnsan kontrolü: `pusu/1` 20:00-22:00 arasındaki konuşmacı değişimleri YouTube'da dinlenip karşılaştırılmalı
  (`utterances/pusu-001.jsonl`).
