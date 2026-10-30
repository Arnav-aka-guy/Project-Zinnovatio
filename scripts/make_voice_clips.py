#!/usr/bin/env python3
"""Make the Punjabi and English voice clips for voice booking.

    python tasks.py voices                 # both languages, female voices, only new or changed clips
    python tasks.py voices --lang en       # English only (or --lang pa)
    python tasks.py voices --voice male    # male voices
    python tasks.py voices --force         # remake everything
    python tasks.py voices --dry-run       # list what would be made, no network
    python tasks.py voices --check         # report clips missing from the manifests

Uses Microsoft's neural voices through the free `edge-tts` package (no key,
needs internet once): Punjabi pa-IN (Vaani / Ojas) and Indian English en-IN
(Neerja / Prabhat). Clips go to web/public/audio/<pa|en>/ with a
manifest.json each, so they ship inside the built web app and play offline.

The text of every clip comes from app/voice/catalog.py, the same file the
engine uses for read-backs, so a clip can never be missing a sentence.
Silence at the start and end of each clip is trimmed in the browser at play
time (sample-accurate), so stitched read-backs have no dead air.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import clock  # noqa: E402  (after the sys.path line above)
from app.voice.catalog import Clip, build_clips  # noqa: E402  (after the sys.path line above)
from app.voice.lexicon import VILLAGES_PA, VillageEntry  # noqa: E402  (after the sys.path line above)

OUT_DIR = ROOT / "web" / "public" / "audio"  # clips go to OUT_DIR/<lang>/
VILLAGES_JSON = ROOT / "app" / "seed" / "villages.json"

# Known neural voices per language. The live voice list is checked first.
FALLBACK_VOICES = {
    "pa": {"female": "pa-IN-VaaniNeural", "male": "pa-IN-OjasNeural"},
    "en": {"female": "en-IN-NeerjaNeural", "male": "en-IN-PrabhatNeural"},
}
LOCALES = {"pa": "pa-in", "en": "en-in"}
DEFAULT_RATE = "-5%"  # a touch slower than default: clearer on a phone speaker


def village_entries() -> list[VillageEntry]:
    entries = list(VILLAGES_PA)
    known = {v.name.lower() for v in entries}
    if VILLAGES_JSON.exists():
        for row in json.loads(VILLAGES_JSON.read_text(encoding="utf-8")):
            name = str(row.get("name", "")).strip()
            if name and name.lower() not in known:
                # No Gurmukhi spelling yet: the voice reads the English name.
                entries.append(VillageEntry(name, name))
                known.add(name.lower())
    return entries


def clip_hash(clip: Clip, voice: str, rate: str, pitch: str) -> str:
    return hashlib.sha1(f"{clip.text}|{voice}|{rate}|{pitch}".encode()).hexdigest()[:12]


def load_manifest(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            pass
    return {"clips": {}}


def write_manifest(path: Path, manifest: dict) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


async def resolve_voice(edge_tts, lang: str, choice: str) -> str:
    if choice.lower().startswith(LOCALES[lang]):
        return choice
    gender = choice if choice in ("female", "male") else "female"
    preferred = FALLBACK_VOICES[lang][gender]
    try:
        voices = await edge_tts.list_voices()
        local = [v for v in voices if str(v.get("Locale", "")).lower() == LOCALES[lang]]
        names = [v["ShortName"] for v in local]
        if preferred in names:
            return preferred
        want = "Female" if gender == "female" else "Male"
        for v in local:
            if v.get("Gender") == want:
                return v["ShortName"]
        if local:
            return local[0]["ShortName"]
    except Exception as exc:  # network trouble: fall back to the known names
        print(f"  (could not list voices: {type(exc).__name__}; using {preferred})")
    return preferred


async def synth_one(edge_tts, clip: Clip, voice: str, rate: str, pitch: str, dest: Path, tries: int = 4) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    delay = 1.5
    for attempt in range(1, tries + 1):
        try:
            data = bytearray()
            comm = edge_tts.Communicate(clip.text, voice, rate=rate, pitch=pitch)
            async for chunk in comm.stream():
                if chunk.get("type") == "audio":
                    data.extend(chunk["data"])
            if len(data) < 1500:
                raise RuntimeError("audio too short")
            tmp.write_bytes(bytes(data))
            tmp.replace(dest)
            return len(data)
        except Exception as exc:
            if attempt == tries:
                raise RuntimeError(f"{clip.id}: {type(exc).__name__}: {exc}") from exc
            await asyncio.sleep(delay)
            delay *= 2
    return 0


async def run(args: argparse.Namespace) -> int:
    langs = ["pa", "en"] if args.lang == "all" else [args.lang]
    code = 0
    for lang in langs:
        print(f"── {lang} ──")
        code = max(code, await run_lang(args, lang))
    return code


async def run_lang(args: argparse.Namespace, lang: str) -> int:
    out_dir = Path(args.out).resolve() / lang
    manifest_path = out_dir / "manifest.json"
    clips = build_clips(village_entries(), lang)
    if args.only:
        prefixes = tuple(p.strip() for p in args.only.split(",") if p.strip())
        clips = [c for c in clips if c.id.startswith(prefixes)]

    manifest = load_manifest(manifest_path)

    if args.check:
        have = manifest.get("clips", {})
        missing = [c.id for c in clips if c.id not in have or not (out_dir / have[c.id]["file"]).exists()]
        print(f"{len(clips) - len(missing)} of {len(clips)} clips present in {out_dir}")
        for cid in missing[:40]:
            print(f"  missing: {cid}")
        return 1 if missing else 0

    if args.dry_run:
        groups: dict[str, int] = {}
        for c in clips:
            groups[c.id.split("/")[0]] = groups.get(c.id.split("/")[0], 0) + 1
        print(f"{len(clips)} clips -> {out_dir}")
        for g, n in groups.items():
            print(f"  {g:8} {n}")
        for c in clips[:8] + [c for c in clips if c.id in ("acres/550", "date/11-15", "village/talwandi_sabo")]:
            print(f"  {c.id:28} {c.text}")
        return 0

    try:
        import edge_tts  # type: ignore
    except ImportError:
        print("edge-tts is not installed. Run:  pip install -r requirements-voice.txt")
        return 2

    voice = await resolve_voice(edge_tts, lang, args.voice)
    print(f"Voice: {voice}  rate {args.rate}  pitch {args.pitch}  ->  {out_dir}")

    old = manifest.get("clips", {})
    new_clips: dict[str, dict] = {}
    todo: list[tuple[Clip, str, Path]] = []
    for c in clips:
        h = clip_hash(c, voice, args.rate, args.pitch)
        rel = f"{c.id}.mp3"
        dest = out_dir / rel
        prev = old.get(c.id)
        if not args.force and prev and prev.get("sha") == h and dest.exists():
            new_clips[c.id] = prev
        else:
            todo.append((c, h, dest))

    print(f"{len(clips) - len(todo)} up to date, {len(todo)} to make")
    sem = asyncio.Semaphore(max(1, args.concurrency))
    failed: list[str] = []
    done = 0

    async def worker(c: Clip, h: str, dest: Path) -> None:
        nonlocal done
        async with sem:
            try:
                size = await synth_one(edge_tts, c, voice, args.rate, args.pitch, dest)
                new_clips[c.id] = {"file": f"{c.id}.mp3", "text": c.text, "sha": h, "bytes": size}
            except Exception as exc:
                failed.append(str(exc))
            done += 1
            if done % 25 == 0 or done == len(todo):
                print(f"  {done}/{len(todo)}")

    await asyncio.gather(*(worker(c, h, d) for c, h, d in todo))

    # Keep entries from a partial --only run that are still valid.
    if args.only:
        for cid, entry in old.items():
            new_clips.setdefault(cid, entry)

    manifest = {
        "version": 1,
        "lang": f"{lang}-IN",
        "voice": voice,
        "rate": args.rate,
        "pitch": args.pitch,
        "generated_at": clock.now_utc().replace(microsecond=0).isoformat(),
        "clips": dict(sorted(new_clips.items())),
    }
    write_manifest(manifest_path, manifest)
    total_kb = sum(int(e.get("bytes", 0)) for e in new_clips.values()) // 1024
    print(f"Manifest: {len(new_clips)} clips, {total_kb} KB -> {manifest_path}")
    if failed:
        print(f"{len(failed)} clips failed (run again to retry):")
        for f in failed[:20]:
            print(f"  {f}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lang", default="all", choices=["all", "pa", "en"], help="which language to make")
    p.add_argument("--voice", default="female", help="female | male | a voice ShortName (pa-IN-... or en-IN-...)")
    p.add_argument("--rate", default=DEFAULT_RATE, help="speaking rate, e.g. -5%% or +0%%")
    p.add_argument("--pitch", default="+0Hz", help="pitch shift, e.g. +0Hz")
    p.add_argument("--out", default=str(OUT_DIR), help="output folder (a <lang> folder is made inside)")
    p.add_argument("--only", default="", help="comma-separated id prefixes, e.g. prompt/,digit/")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--force", action="store_true", help="remake every clip")
    p.add_argument("--dry-run", action="store_true", help="list clips, make nothing")
    p.add_argument("--check", action="store_true", help="report missing clips and exit")
    args = p.parse_args(argv)
    if args.voice not in ("female", "male") and not args.voice.lower().startswith(("pa-in-", "en-in-")):
        p.error("--voice must be female, male, or a pa-IN-... / en-IN-... voice name")
    if args.voice.lower().startswith("pa-in-") and args.lang == "all":
        args.lang = "pa"
    if args.voice.lower().startswith("en-in-") and args.lang == "all":
        args.lang = "en"
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
