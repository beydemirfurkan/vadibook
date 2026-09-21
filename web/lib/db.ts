import "server-only";
import Database from "better-sqlite3";
import path from "node:path";
import type { Series } from "./format";

export type Part = { yt_id: string; title: string; offset_sec: number; duration_sec: number | null };
export type EpisodeRow = {
  key: string;
  series: Series;
  no: number;
  title: string;
  yt_id: string;
  duration_sec: number;
  parts: Part[];
};
export type EpisodeStats = { utterances: number; speakers: number; spokenSec: number };
export type TimelineTurn = { speaker: string; start: number; end: number };
export type CorpusStats = { episodes: number; utterances: number; hours: number; spokenHours: number };

let db: Database.Database | null = null;

function open(): Database.Database {
  if (!db) {
    const file = path.resolve(/* turbopackIgnore: true */ process.cwd(), process.env.VADIBOOK_SQLITE ?? "../data/private/vadibook.sqlite");
    db = new Database(file, { readonly: true, fileMustExist: true });
  }
  return db;
}

type RawEpisode = Omit<EpisodeRow, "parts"> & { parts: string };

function toEpisode(r: RawEpisode): EpisodeRow {
  return { ...r, parts: JSON.parse(r.parts) as Part[] };
}

export function getEpisode(series: Series, no: number): EpisodeRow | null {
  const r = open().prepare("select * from episodes where series = ? and no = ?").get(series, no) as RawEpisode | undefined;
  return r ? toEpisode(r) : null;
}

export function listEpisodes(): EpisodeRow[] {
  const rows = open().prepare("select * from episodes order by series, no").all() as RawEpisode[];
  return rows.map(toEpisode);
}

export function adjacentEpisodes(series: Series, no: number): { prev: EpisodeRow | null; next: EpisodeRow | null } {
  const d = open();
  const prev = d.prepare("select * from episodes where series = ? and no < ? order by no desc limit 1").get(series, no) as RawEpisode | undefined;
  const next = d.prepare("select * from episodes where series = ? and no > ? order by no asc limit 1").get(series, no) as RawEpisode | undefined;
  return { prev: prev ? toEpisode(prev) : null, next: next ? toEpisode(next) : null };
}

export function episodeStats(key: string): EpisodeStats {
  const r = open()
    .prepare("select count(*) as utterances, count(distinct speaker) as speakers, coalesce(sum(end - start), 0) as spokenSec from utterances where ep_key = ?")
    .get(key) as EpisodeStats;
  return r;
}

/** Speaker turns without any text — safe to ship to the browser. */
export function speakerTimeline(key: string): TimelineTurn[] {
  return open().prepare("select speaker, start, end from utterances where ep_key = ? order by start").all(key) as TimelineTurn[];
}

export function corpusStats(): CorpusStats {
  const d = open();
  const e = d.prepare("select count(*) as episodes, coalesce(sum(duration_sec), 0) as sec from episodes").get() as { episodes: number; sec: number };
  const u = d.prepare("select count(*) as utterances, coalesce(sum(end - start), 0) as spoken from utterances").get() as { utterances: number; spoken: number };
  return { episodes: e.episodes, utterances: u.utterances, hours: e.sec / 3600, spokenHours: u.spoken / 3600 };
}
