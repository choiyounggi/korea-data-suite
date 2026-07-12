"""Regenerate app/apis/realestate/regions.py from the 법정동코드 (legal-dong code) CSV.

Source
------
국토교통부_법정동코드 (https://www.data.go.kr/data/15123287) — a tab-separated,
UTF-8 file of 10-digit 법정동코드, 법정동명, 폐지여부. A sigungu-level row is a code
whose last five digits are "00000" (읍면동/리 part empty) and whose 시군구 part
(digits 3-5) is non-zero (excludes 시도-level rows). The first five digits are the
LAWD_CD that the MOLIT real-estate endpoints accept.

Verification
------------
MOLIT was probed live for representative codes: 구 codes (11680, 41111) and 구-less
시 codes (36110) return rows; a 구-having 시's aggregate code (41110) and an invalid
code (99999) return zero rows. So including every '존재' sigungu code is safe — the
few 시-aggregates simply yield empty partitions and are skipped, with no duplication.

name_en
-------
Hand-verified Seoul name_en values in the existing module are preserved (prefixed
with the sido). Every other sigungu name is romanized (Revised Romanization via
hangul-romanize) — display-only, best-effort.

Usage
-----
    uv run --with hangul-romanize python scripts/gen_regions.py <ldong.csv> > out.py
"""
import sys

from hangul_romanize import Transliter
from hangul_romanize.rule import academic

try:  # harvest the existing verified Seoul name_en values
    from app.apis.realestate.regions import REGIONS as OLD
except Exception:  # pragma: no cover - first run / import path
    OLD = {}

_t = Transliter(academic)

SIDO_EN = {
    "서울특별시": "Seoul", "부산광역시": "Busan", "대구광역시": "Daegu",
    "인천광역시": "Incheon", "광주광역시": "Gwangju", "대전광역시": "Daejeon",
    "울산광역시": "Ulsan", "세종특별자치시": "Sejong",
    "경기도": "Gyeonggi-do", "강원도": "Gangwon-do", "강원특별자치도": "Gangwon-do",
    "충청북도": "Chungcheongbuk-do", "충청남도": "Chungcheongnam-do",
    "전라북도": "Jeollabuk-do", "전북특별자치도": "Jeollabuk-do",
    "전라남도": "Jeollanam-do", "경상북도": "Gyeongsangbuk-do",
    "경상남도": "Gyeongsangnam-do", "제주특별자치도": "Jeju-do", "제주도": "Jeju-do",
}
SUFFIX_EN = {"시": "-si", "군": "-gun", "구": "-gu"}


def rom(word: str) -> str:
    s = _t.translit(word).replace("-", "").strip()
    return (s[:1].upper() + s[1:]) if s else s


def rom_token(tok: str) -> str:
    if tok and tok[-1] in SUFFIX_EN:
        return rom(tok[:-1]) + SUFFIX_EN[tok[-1]]
    return rom(tok)


def main(csv_path: str) -> None:
    rows: list[tuple[str, str]] = []
    with open(csv_path, encoding="utf-8") as f:
        next(f)  # header
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            code10, name, status = parts[0], parts[1], parts[2]
            if status != "존재" or not code10.isdigit() or len(code10) != 10:
                continue
            if code10[5:] != "00000" or code10[2:5] == "000":
                continue
            rows.append((code10[:5], name))
    rows.sort()

    print("REGIONS: dict[str, dict[str, str]] = {")
    for code, name in rows:
        tokens = name.split()
        sido_en = SIDO_EN.get(tokens[0]) or rom(tokens[0])
        rest = tokens[1:]
        if code in OLD:
            name_en = f"{sido_en} {OLD[code]['name_en']}"
        elif rest:
            name_en = sido_en + " " + " ".join(rom_token(t) for t in rest)
        else:
            name_en = sido_en
        print(f'    "{code}": {{"name_ko": "{name}", "name_en": "{name_en}"}},')
    print("}")
    print("\n\ndef is_valid_region(code: str) -> bool:")
    print("    return code in REGIONS")


if __name__ == "__main__":
    main(sys.argv[1])
