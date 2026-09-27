"""surge_data/ 기록으로 정적 사이트 (site/index.html) 를 만든다.

    python -m surge.site

추천일 D 의 종목은 D 다음 거래일 스냅샷 (surge_data/daily) 의 시가로 실제 수익을 계산한다.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "surge_data"
OUT = ROOT / "site" / "public" / "index.html"
KST = ZoneInfo("Asia/Seoul")
COST = 0.002


def load_picks() -> list[dict]:
    out = []
    for p in sorted(DATA.glob("picks/*.json")):
        d = json.loads(p.read_text())
        d["file_date"] = p.stem
        out.append(d)
    return out


def load_opens() -> dict[str, pd.Series]:
    """스냅샷 날짜 -> code 별 시가."""
    opens = {}
    for p in sorted(DATA.glob("daily/*.csv")):
        df = pd.read_csv(p, dtype={"code": str})
        if df.empty:
            continue
        bar = str(df["date"].iloc[0])[:10]
        opens[bar] = df.set_index("code")["open"]
    return opens


def realize(picks: list[dict], opens: dict[str, pd.Series]) -> list[dict]:
    """각 추천에 다음 거래일 시가와 수익률을 붙인다."""
    bars = sorted(opens)
    for d in picks:
        if d.get("status") != "ok":
            continue
        nxt = [b for b in bars if b > d["bar_date"]]
        d["exit_date"] = nxt[0] if nxt else None
        for p in d["picks"]:
            p["exit"] = p["ret"] = None
            if nxt:
                o = opens[nxt[0]].get(p["code"])
                if o and o > 0:
                    p["exit"] = int(o)
                    p["ret"] = o / p["price"] - 1 - COST
        rets = [p["ret"] for p in d["picks"] if p["ret"] is not None]
        d["day_ret"] = sum(rets) / len(rets) if rets else None
    return picks


def pct(v, digits: int = 2) -> str:
    return "-" if v is None else f"{v * 100:+.{digits}f}%"


def cls(v) -> str:
    if v is None:
        return ""
    return " class='up'" if v > 0 else " class='down'" if v < 0 else ""


def render(picks: list[dict]) -> str:
    now = datetime.now(KST)
    done = [d for d in picks if d.get("status") == "ok"]
    latest = done[-1] if done else None
    closed = [d for d in picks if d.get("status") == "closed"]
    e = html.escape

    parts = [f"<header><h1>종목 추천</h1><p class='muted'>종가 매수 · 익일 시가 매도 · 갱신 {now:%m/%d %H:%M}</p></header>"]

    # 누적 성적
    days = [d for d in done if d.get("day_ret") is not None]
    if days:
        rets = [d["day_ret"] for d in days]
        eq = 1.0
        for r in rets:
            eq *= 1 + r
        wins = sum(1 for r in rets if r > 0)
        parts.append(
            "<section class='summary'>"
            f"<div><span>실현 일수</span><b>{len(rets)}일</b></div>"
            f"<div><span>일평균</span><b{cls(sum(rets)/len(rets))}>{pct(sum(rets)/len(rets))}</b></div>"
            f"<div><span>승률</span><b>{wins/len(rets):.0%}</b></div>"
            f"<div><span>누적</span><b{cls(eq-1)}>{pct(eq-1)}</b></div>"
            "</section>")

    # 최신 추천
    if latest:
        status = "결과 대기" if latest.get("exit_date") is None else f"{latest['exit_date'][5:]} 시가 매도 결과"
        parts.append(f"<section><h2>{e(latest['bar_date'][5:])} 추천 <small class='muted'>{e(status)}</small></h2>")
        parts.append("<table><thead><tr><th>종목</th><th>매수</th><th>기대</th><th>매도</th><th>실현</th></tr></thead><tbody>")
        for p in latest["picks"]:
            parts.append(
                f"<tr><td><b>{e(p['name'])}</b><br><small class='muted'>{e(p['code'])} · {e(p['reasons'])}</small></td>"
                f"<td>{p['price']}</td><td{cls(p['exp'])}>{pct(p['exp'], 1)}</td>"
                f"<td>{p['exit'] if p['exit'] else '-'}</td><td{cls(p['ret'])}>{pct(p['ret'])}</td></tr>")
        parts.append("</tbody></table>")
        ho = latest.get("holdout", {})
        if ho:
            parts.append(f"<p class='muted'>모델 검증 최근 {ho.get('days')}거래일 · 비용 후 일평균 {pct(ho.get('pick_ret'))} · 승률 {ho.get('win_days', 0):.0%}</p>")
        parts.append("</section>")

    # 날짜별 기록
    if len(done) > 1:
        parts.append("<section><h2>기록</h2><table><thead><tr><th>추천일</th><th>종목</th><th>실현 평균</th></tr></thead><tbody>")
        for d in reversed(done[:-1]):
            names = " · ".join(f"{e(p['name'])} <span{cls(p['ret'])}>{pct(p['ret'], 1)}</span>" for p in d["picks"])
            parts.append(f"<tr><td>{e(d['bar_date'][5:])}</td><td>{names}</td><td{cls(d.get('day_ret'))}>{pct(d.get('day_ret'))}</td></tr>")
        parts.append("</tbody></table></section>")

    if closed:
        parts.append("<p class='muted'>휴장 " + " · ".join(e(d["file_date"][4:6] + "/" + d["file_date"][6:]) for d in closed) + "</p>")
    parts.append("<footer class='muted'>참고용이다. 투자 판단과 손실 책임은 본인에게 있다.</footer>")

    body = "\n".join(parts)
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>종목 추천</title>
<style>
:root{{--bg:#fff;--fg:#111;--muted:#6b7280;--line:#e5e7eb;--card:#f6f7f9;--up:#d12f2f;--down:#1f5fd1}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1115;--fg:#e8eaed;--muted:#9aa0a6;--line:#2a2e35;--card:#181b21;--up:#ff6b6b;--down:#6ea8ff}}}}
*{{box-sizing:border-box}}body{{margin:0;padding:16px;max-width:760px;margin-inline:auto;background:var(--bg);color:var(--fg);font:16px/1.5 -apple-system,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}}
h1{{font-size:24px;margin:0 0 4px}}h2{{font-size:18px;margin:28px 0 10px}}h2 small{{font-size:13px;font-weight:400;margin-left:6px}}
.muted{{color:var(--muted)}}small{{font-size:12px}}.up{{color:var(--up)}}.down{{color:var(--down)}}
table{{width:100%;border-collapse:collapse;font-size:15px}}th,td{{padding:10px 6px;border-bottom:1px solid var(--line);text-align:right;vertical-align:top}}
th:first-child,td:first-child{{text-align:left}}th{{font-weight:500;color:var(--muted);font-size:13px}}
.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:16px}}.summary div{{background:var(--card);border-radius:10px;padding:10px}}
.summary span{{display:block;font-size:12px;color:var(--muted)}}.summary b{{font-size:18px}}
footer{{margin-top:32px;font-size:13px}}
@media (max-width:480px){{body{{padding:12px}}.summary{{grid-template-columns:repeat(2,1fr)}}table{{font-size:14px}}}}
</style></head><body>
{body}
</body></html>"""


def build() -> Path:
    picks = realize(load_picks(), load_opens())
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render(picks), encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print(build())
