/**
 * Starter dictionary of names worth counting per episode: characters and organisations from the
 * show. `tokens` are ASCII-folded, lowercase word prefixes matched against `text_ascii`
 * (" polat" matches "Polat", "Polat'ın", "Polat'a"). Ambiguous everyday words (kara, aslan, aziz)
 * are matched with their full name only. Replaced by data/public/characters.json in Faz 3.
 */
export type NameEntry = { name: string; tokens: string[]; kind: "character" | "org" };

export const NAMES: NameEntry[] = [
  { name: "Polat Alemdar", tokens: ["polat"], kind: "character" },
  { name: "Memati", tokens: ["memati"], kind: "character" },
  { name: "Abdülhey", tokens: ["abdulhey"], kind: "character" },
  { name: "Süleyman Çakır", tokens: ["cakir"], kind: "character" },
  { name: "Elif", tokens: ["elif"], kind: "character" },
  { name: "Aslan Akbey", tokens: ["aslan akbey", "akbey"], kind: "character" },
  { name: "Laz Ziya", tokens: ["laz ziya", "ziya"], kind: "character" },
  { name: "Seyfo Dayı", tokens: ["seyfo"], kind: "character" },
  { name: "Nesrin", tokens: ["nesrin"], kind: "character" },
  { name: "Güllü", tokens: ["gullu"], kind: "character" },
  { name: "Tuncay", tokens: ["tuncay"], kind: "character" },
  { name: "Kılıç", tokens: ["kilic"], kind: "character" },
  { name: "Mehmet Karahanlı", tokens: ["karahanli"], kind: "character" },
  { name: "Nizamettin Güneş", tokens: ["nizamettin"], kind: "character" },
  { name: "Testere Necmi", tokens: ["testere", "necmi"], kind: "character" },
  { name: "Zaza", tokens: ["zaza"], kind: "character" },
  { name: "Kaşifoğlu", tokens: ["kasifoglu"], kind: "character" },
  { name: "İskender Büyük", tokens: ["iskender"], kind: "character" },
  { name: "Ömer Baba", tokens: ["omer baba"], kind: "character" },
  { name: "Erhan", tokens: ["erhan"], kind: "character" },
  { name: "Cahit", tokens: ["cahit"], kind: "character" },
  { name: "Safiye", tokens: ["safiye"], kind: "character" },
  { name: "Ebru", tokens: ["ebru"], kind: "character" },
  { name: "Leyla", tokens: ["leyla"], kind: "character" },
  { name: "Asya", tokens: ["asya"], kind: "character" },
  { name: "Aron Feller", tokens: ["aron", "feller"], kind: "character" },
  { name: "Muro", tokens: ["muro"], kind: "character" },
  { name: "Halo Elvan", tokens: ["elvan"], kind: "character" },
  { name: "Hüsrev Ağa", tokens: ["husrev"], kind: "character" },
  { name: "Pusat", tokens: ["pusat"], kind: "character" },
  { name: "Zülfikar", tokens: ["zulfikar"], kind: "character" },
  { name: "Deli Hüsnü", tokens: ["husnu"], kind: "character" },
  { name: "Baybars", tokens: ["baybars"], kind: "character" },
  { name: "Tapınakçılar", tokens: ["tapinak"], kind: "org" },
  { name: "KGT", tokens: ["kgt"], kind: "org" },
  { name: "Konsey", tokens: ["konsey"], kind: "org" },
  { name: "Şedid", tokens: ["sedid"], kind: "org" },
  { name: "Siyah Sancak", tokens: ["siyah sancak"], kind: "org" },
  { name: "Gladio", tokens: ["gladio"], kind: "org" },
  { name: "Mossad", tokens: ["mossad"], kind: "org" },
  { name: "CIA", tokens: ["cia"], kind: "org" },
  { name: "Ergenekon", tokens: ["ergenekon"], kind: "org" },
  { name: "derin devlet", tokens: ["derin devlet"], kind: "org" },
];
