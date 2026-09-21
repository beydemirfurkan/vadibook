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

## Bekleyen

- Diarization (pyannote community-1) ölçümü: HF token gerekiyor. RTF ve konuşmacı sayısı buraya eklenecek.
- İnsan kontrolü: diarization bitince 2-3 dk'lık bir kesitte konuşmacı sınırları ve isimler elle dinlenmeli.
