"""Зведення українських текстів Units/*.txt з патчем балансу репаку (WC3Patcher у теці гри).

Патч репаку кладе в Units/ власні *Strings.txt: нові секції (пасивні індикатори), нові ключі (бафи, Untip «до дослідження»)
і блоки характеристик в описах (дальність, перезарядка…). Наші файли перекладу перекривають ці файли цілком —
без зведення частина кнопок лишається без підказок. Тут, під час збірки й лише локально:
  * відсутня секція / ключ → переклад (пам'ять перекладів «англ. → укр.» з пар патч↔переклад, шаблони, словничок),
    а якщо не вийшло — англійський текст патчу (краще, ніж порожня підказка);
  * наявний опис без характеристик → дописується перекладений блок характеристик патчу.
Тексти патчу беруться з гри користувача й у репозиторій не потрапляють; словничок — data/text-overrides/repack-glossary.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

GLOSSARY = Path(__file__).resolve().parent.parent / "data/text-overrides/repack-glossary.json"
TEXT_KEYS = {"name", "tip", "ubertip", "untip", "unubertip", "bufftip", "buffubertip", "description", "researchtip",
             "researchubertip", "revivetip", "awakentip", "tooltip", "casterupgradename", "casterupgradetip"}
DESC_KEYS = {"ubertip", "unubertip", "buffubertip", "researchubertip"}
STATS = re.compile(r"\|n(?:\|n)?(?=\|c[fF]{2}(?:99ccff|b0b0b0))")
LINE = re.compile(r"^\|c[fF]{2}([0-9a-fA-F]{6})(.+?)(:?)\|[rR](.*)$")
HK = re.compile(r"\s*\(\|c[fF]{2}[0-9a-fA-F]{6}.\|[rR]\)|\|c[fF]{2}[0-9a-fA-F]{6}|\|[rR]")


def find_sources(game: Path | None) -> list[Path]:
    """Теки з рядками патчу репаку (macOS: …/Warcraft III.app/Contents/Resources/WC3Patcher/data)."""
    if not game:
        return []
    for pat in ("*/*/Contents/Resources/WC3Patcher/data", "*/WC3Patcher/data", "WC3Patcher/data"):
        for d in sorted(Path(game).glob(pat)):
            got = [p for p in (d / "patch/Payload/Strings", d / "hero_profiles/base") if p.is_dir()]
            if got:
                return got
    return []


def parse(text: str) -> dict[str, dict[str, str]]:
    d: dict[str, dict[str, str]] = {}
    sec = None
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("//"):
            continue
        m = re.match(r"\[(.+?)\]", s)
        if m:
            sec = d.setdefault(m.group(1).lower(), {"": m.group(1)})
        elif sec is not None and "=" in s:
            k, v = s.split("=", 1)
            sec.setdefault(k.strip().lower(), v.strip())
            sec.setdefault("\0" + k.strip().lower(), k.strip())          # оригінальне написання ключа
    return d


def norm(x: str) -> str:
    return re.sub(r"[^a-z]", "", x.lower())


def unq(v: str) -> str:
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] == '"' else v


def split_stats(v: str) -> tuple[str, str]:
    """(опис, блок характеристик із провідним |n|n або ''), без лапок."""
    v = unq(v)
    m = STATS.search(v)
    return (v[:m.start()], v[m.start():]) if m else (v, "")


def levels(v: str) -> list[str]:
    """Значення по рівнях: «"a","b","c"» → [a, b, c]; звичайне → [v без лапок]."""
    return unq(v.strip()).split('","')


def english_left(v: str) -> bool:
    return bool(re.search(r"[A-Za-z]{4,}", re.sub(r"<[^>]*>|\|c[fF]{2}[0-9a-fA-F]{6}|\|[nrNR]|%\w", "", v)))


class Translator:
    def __init__(self, patch: dict, ua: dict, gloss: dict):
        self.ua, self.g = ua, gloss
        self.tm: dict[str, str] = {}
        self.by_name: dict[str, str] = {}
        self.norm: dict[str, str] = {}
        for prio in ("name", "bufftip", "tip", "untip", "ubertip", "buffubertip"):
            for s, kv in patch.items():
                if s in ua and prio in kv and prio in ua[s]:
                    en, uk = HK.sub("", split_stats(kv[prio])[0]).strip(), HK.sub("", split_stats(ua[s][prio])[0]).strip()
                    if en and uk and not english_left(uk):
                        self.tm.setdefault(en, uk)
                if prio == "name" and "name" in kv:                       # назва → секція дослідження (R…) має перевагу
                    n = unq(kv["name"])
                    if n not in self.by_name or (s.startswith("r") and not self.by_name[n].startswith("r")):
                        self.by_name[n] = s

    def term(self, x: str) -> str | None:
        x = x.strip()
        if x in self.tm or x in self.g["labels"]:
            return self.tm.get(x) or self.g["labels"][x]
        if x.endswith(".") and self.term(x[:-1]):
            return self.term(x[:-1]) + "."
        if not self.norm:
            for en, uk in self.tm.items():
                self.norm.setdefault(norm(en), uk)
        if norm(x) in self.norm:                                         # «Shock Wave» ≈ «Shockwave»
            return self.norm[norm(x)]
        m = re.fullmatch(r"(.+?)\s*\((.+)\)", x)                         # «Blizzard (creep)» → «Хуртовина (крип)»
        if m and self.term(m.group(1)):
            inner = ", ".join(self.g["words"].get(w.strip(), w.strip()) for w in m.group(2).split(","))
            return f"{self.term(m.group(1))} ({inner})"
        m = re.fullmatch(r"(.+?)\s*\(?(?:[Ll]evel|level) (\d+)\)?", x)
        if m and self.term(m.group(1)):
            return f"{self.term(m.group(1))}, рівень {m.group(2)}"
        return None

    def value(self, v: str) -> str:
        v2, lead = v.strip(), v[:len(v) - len(v.lstrip())]
        if v2 in self.g["values"]:
            return lead + self.g["values"][v2]
        return re.sub(r"\b(sec)\b", "с", " ".join(self.g["values"].get(w, w) for w in v.split(" ")))

    def line(self, seg: str) -> str:
        m = LINE.match(seg)
        if m:
            color, lab, colon, rest = m.groups()
            if not colon and not rest:                                   # «|cffffcc00Attacks land units.|r», «Level 1»
                t = self.g["lines"].get(lab) or self.term(lab) or re.sub(r"^Level\b", "Рівень", lab)
                return f"|cff{color}{t}|r"
            t = self.g["labels"].get(lab) or self.term(lab) or lab
            return f"|cff{color}{t}{colon}|r{self.value(rest) if rest else ''}"
        return self.g["lines"].get(seg.strip(), self.tm.get(seg.strip(), seg))

    def stats(self, block: str) -> str:
        lead = re.match(r"(?:\|n)*", block).group(0)
        return lead + "|n".join(self.line(s) for s in block[len(lead):].split("|n"))

    def sentence(self, s: str, sec: str) -> str:
        own = HK.sub("", unq(self.ua.get(sec, {}).get("name", ""))) or None
        if s in self.g["lines"]:
            return self.g["lines"][s]
        for pat, tpl in ((r"Train (.+)", "Тренувати: {}"), (r"Build (.+)", "Звести: {}"), (r"Summon (.+)", "Закликати: {}"),
                         (r"Research (.+)", "Дослідити: {}"), (r"Upgrade to (.+)", "Вдосконалити до: {}")):
            m = re.fullmatch(pat, s)
            if m:
                return tpl.format(own or self.term(m.group(1)) or m.group(1))
        m = re.fullmatch(r"This unit is affected by (.+?)\.", s)
        if m:
            return f"Цей юніт під дією: {self.term(m.group(1)) or m.group(1)}."
        m = re.fullmatch(r"(.+) unit\.", s)
        if m and m.group(1) in self.g["values"]:
            return f"Юніт: {self.g['values'][m.group(1)]}."
        m = re.fullmatch(r"After research, (.+)", s)
        if m:
            return self.after_research(s, sec) or s
        return self.term(s) or s

    def after_research(self, s: str, sec: str) -> str | None:
        ref = re.search(r"<(R\w{3}),", s)
        up = ref.group(1).lower() if ref else None
        if not up:
            nm = unq(self.ua.get(sec, {}).get("\0src_name", "")) or None
            up = self.by_name.get(nm) if nm else None
        u = self.ua.get(up or "", {})
        if "ubertip" not in u:
            return None
        first = re.match(r'"((?:[^"])*)"|([^,]*)', u["ubertip"])
        body = (first.group(1) or first.group(2) or "").strip()
        return f"Після дослідження «{HK.sub('', unq(u.get('name', up)))}»: {body}"

    def text(self, v: str, sec: str) -> str:
        if len(levels(v)) > 1:
            return '","'.join(self.text(lv, sec) for lv in levels(v))
        base, tail = split_stats(v)
        parts = base.split("|n|n")
        one = lambda p: self.line(p) if LINE.match(p) else self.sentence(p, sec) if p else p  # noqa: E731
        out = "|n|n".join("|n".join(one(p) for p in para.split("|n")) for para in parts)
        return out + (self.stats(tail) if tail else "")


def _q(v: str) -> str:
    return f'"{v}"'


def with_stats(tr: Translator, ua_val: str, patch_val: str) -> str | None:
    """Наш опис + перекладені характеристики патчу (по рівнях). None — нема чого дописувати або рівні не збігаються."""
    if "|cff99ccff" in ua_val.lower():
        return None
    pl, ul = levels(patch_val), levels(ua_val)
    tails = [split_stats(x)[1] for x in pl]
    if len(pl) != len(ul) or not any(tails):                              # різна кількість рівнів — не вгадуємо
        return None
    return _q('","'.join(u + (tr.stats(t) if t else "") for u, t in zip(ul, tails, strict=True)))


def plan(patch: dict, ua: dict, gloss: dict) -> tuple[dict, dict, dict]:
    """→ (ops для text_overrides: {sec: {key: op}}, нові секції {sec: {key: value}}, статистика)."""
    tr = Translator(patch, ua, gloss)
    ops: dict = {}
    new: dict = {}
    st = {"keys": 0, "sections": 0, "stats": 0, "english": 0}
    for s, kv in patch.items():
        keys = [k for k in kv if k and not k.startswith("\0")]
        if s not in ua:
            ua_names = {"\0src_name": kv.get("name", "")}
            tr.ua[s] = ua_names
            body = {}
            for k in keys:
                txt = k.split(":")[0] in TEXT_KEYS
                val = _q(tr.text(kv[k], s)) if txt else kv[k]
                st["english"] += txt and english_left(val)
                body[kv["\0" + k]] = val
            new[kv[""]] = body
            st["sections"] += 1
            continue
        for k in keys:
            v = kv[k]
            if k not in ua[s]:
                same = next((ua[s][k2] for k2 in ua[s] if k2 and not k2.startswith("\0") and k2 in kv and kv[k2] == v), None)
                txt = k.split(":")[0] in TEXT_KEYS
                if same and k in DESC_KEYS:
                    same = with_stats(tr, same, v) or same
                val = v if not unq(v).strip() else same or (_q(tr.text(v, s)) if txt else v)
                if txt and english_left(val):
                    st["english"] += 1
                    st.setdefault("english_keys", []).append(f"{ua[s]['']}.{kv[chr(0) + k]}")
                ops.setdefault(s, {})[k] = {"section": ua[s][""], "key": kv["\0" + k], "set": unq(val) if txt else val}
                st["keys"] += 1
            elif k in DESC_KEYS and (joined := with_stats(tr, ua[s][k], v)):
                ops.setdefault(s, {})[k] = {"section": ua[s][""], "key": ua[s]["\0" + k], "set": joined}
                st["stats"] += 1
    return ops, new, st


def merge(files: dict[str, str], sources: list[Path], gloss_path: Path | None = None) -> tuple[dict[str, str], dict]:
    """files: {rel Units/*.txt: текст}. Повертає змінені тексти й статистику; патч репаку не змінюється."""
    import text_overrides
    gloss = json.loads(Path(gloss_path or GLOSSARY).read_text(encoding="utf-8"))
    ua_all: dict = {}
    for t in files.values():
        for s, kv in parse(t).items():
            ua_all.setdefault(s, {}).update({k: v for k, v in kv.items() if k not in ua_all.get(s, {})})
    patch_files: dict[str, dict] = {}
    for src in sources:
        for p in sorted(src.glob("*[Ss]trings.txt")):
            for s, kv in parse(p.read_text(encoding="utf-8-sig", errors="replace")).items():
                patch_files.setdefault(p.name.lower(), {}).setdefault(s, kv)
    patch_all = {s: kv for d in patch_files.values() for s, kv in d.items()}
    ops, new, st = plan(patch_all, ua_all, gloss)
    owner = {}                                                          # секція → наш файл, де вона є
    for rel, t in files.items():
        for s in parse(t):
            owner.setdefault(s, rel)
    by_file: dict[str, dict] = {}
    for s, o in ops.items():
        by_file.setdefault(owner[s], {})[s] = o
    lower = {Path(r).name.lower(): r for r in files}
    for fname, secs in patch_files.items():
        for s in secs:
            sec_name = next((n for n in new if n.lower() == s), None)
            if sec_name and fname in lower:
                by_file.setdefault(lower[fname], {}).setdefault("\0new", {})[sec_name] = new.pop(sec_name)
    out = {}
    for rel, o in by_file.items():
        added = o.pop("\0new", {})
        text, _, _ = text_overrides.apply(files[rel], o, rel)
        for sec, body in added.items():
            text = text.rstrip("\n") + f"\n\n[{sec}]\n" + "".join(f"{k}={v}\n" for k, v in body.items())
        out[rel] = text
    st["skipped_sections"] = len(new)
    return out, st
