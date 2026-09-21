import Link from "next/link";
import { SearchBox } from "@/components/SearchBox";

export default function NotFound() {
  return (
    <div className="rise mx-auto max-w-2xl space-y-8 pt-16 text-center">
      <p className="badge">Kayıt bulunamadı</p>
      <h1 className="steel-text font-display text-4xl sm:text-5xl">Bu Vadide Böyle Bir Yer Yok.</h1>
      <p className="font-body text-xl text-fg-2">
        Aradığın sayfa ya hiç olmadı ya da sis içinde kayboldu. Bir isim, bir cümle yaz; oradan devam edelim.
      </p>
      <SearchBox size="hero" />
      <p className="font-mono text-[0.68rem] uppercase tracking-[0.16em]">
        <Link href="/" className="text-steel hover:text-moon">
          ← Ana sayfa
        </Link>
      </p>
    </div>
  );
}
