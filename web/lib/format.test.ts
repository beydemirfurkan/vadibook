import { describe, expect, it } from "vitest";
import { episodeHref, fmtTime, renderSnippet, seriesName, speakerLabel } from "./format";

describe("fmtTime", () => {
  it("formats minutes and seconds", () => {
    expect(fmtTime(83)).toBe("1:23");
    expect(fmtTime(5)).toBe("0:05");
  });
  it("adds hours when needed", () => {
    expect(fmtTime(3661)).toBe("1:01:01");
  });
  it("floors fractional seconds", () => {
    expect(fmtTime(59.9)).toBe("0:59");
  });
});

describe("speakerLabel", () => {
  it("turns raw diarization labels into a neutral Turkish label", () => {
    expect(speakerLabel("p1:SPEAKER_07")).toBe("Konuşmacı 7");
    expect(speakerLabel("p2:SPEAKER_00")).toBe("Konuşmacı 0");
  });
  it("marks unknown speakers", () => {
    expect(speakerLabel("p1:UNK")).toBe("Bilinmeyen");
  });
});

describe("seriesName / episodeHref", () => {
  it("names both series", () => {
    expect(seriesName("kv")).toBe("Kurtlar Vadisi");
    expect(seriesName("pusu")).toBe("Kurtlar Vadisi Pusu");
  });
  it("builds episode links", () => {
    expect(episodeHref("pusu", 17)).toBe("/bolum/pusu/17");
  });
});

describe("renderSnippet", () => {
  it("escapes HTML but keeps our own mark tags", () => {
    const html = renderSnippet("<script>x</script> <mark>Polat</mark> & co");
    expect(html).toBe("&lt;script&gt;x&lt;/script&gt; <mark>Polat</mark> &amp; co");
  });
});
