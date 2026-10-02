#!/usr/bin/env python3
"""Claude 일간/주간/월간 토큰 사용량·잔량을 Telegram으로 알려주는 스크립트.

Anthropic Admin API(usage_report/messages)로 사용량을 조회하고,
직접 설정한 한도(budget)와 비교해 잔량을 계산합니다. 표준 라이브러리만 사용합니다.

환경변수
  ANTHROPIC_ADMIN_KEY   Admin API 키 (sk-ant-admin...)
  TELEGRAM_BOT_TOKEN    BotFather에서 발급받은 봇 토큰
  TELEGRAM_CHAT_ID      알림 받을 채팅 ID
  LIMIT_DAILY / LIMIT_WEEKLY / LIMIT_MONTHLY   토큰 한도 (미설정 시 사용량만 표시)
  WARN_PERCENT          이 사용률(%) 이상이면 경고 (기본 80)
  ALWAYS_NOTIFY         true면 경고가 없어도 항상 발송 (기본 true)
  DRY_RUN               true면 Telegram 발송 없이 출력만
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_URL = "https://api.anthropic.com/v1/organizations/usage_report/messages"
KST = timezone(timedelta(hours=9))


def env_bool(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "y")


def env_int(name):
    v = os.environ.get(name, "").strip()
    return int(v.replace(",", "")) if v else None


def http_json(req):
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {e.url}: {e.read().decode(errors='replace')[:300]}")


def fetch_daily_tokens(admin_key, start, end):
    """[start, end) 구간의 일별 토큰 합계를 {date: tokens}로 반환."""
    totals, page = {}, None
    while True:
        q = {
            "starting_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ending_at": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bucket_width": "1d",
            "limit": 31,
        }
        if page:
            q["page"] = page
        req = urllib.request.Request(
            f"{API_URL}?{urllib.parse.urlencode(q)}",
            headers={"x-api-key": admin_key, "anthropic-version": "2023-06-01"},
        )
        body = http_json(req)
        for bucket in body.get("data", []):
            day = bucket["starting_at"][:10]
            for r in bucket.get("results", []):
                cc = r.get("cache_creation") or {}
                totals[day] = totals.get(day, 0) + (
                    r.get("uncached_input_tokens", 0)
                    + r.get("cache_read_input_tokens", 0)
                    + cc.get("ephemeral_1h_input_tokens", 0)
                    + cc.get("ephemeral_5m_input_tokens", 0)
                    + r.get("output_tokens", 0)
                )
        if body.get("has_more") and body.get("next_page"):
            page = body["next_page"]
        else:
            return totals


def bar(pct, width=10):
    filled = min(width, round(pct / 100 * width))
    return "█" * filled + "░" * (width - filled)


def fmt(n):
    return f"{n:,}"


def build_message(totals, limits, warn, now):
    today = now.date()
    periods = {
        "일간": (today, limits["일간"]),
        "주간": (today - timedelta(days=today.weekday()), limits["주간"]),  # 월요일 시작
        "월간": (today.replace(day=1), limits["월간"]),
    }
    lines, warned = [f"📊 Claude 토큰 사용 현황 ({now:%Y-%m-%d %H:%M} KST)", ""], False
    for name, (since, limit) in periods.items():
        used = sum(v for d, v in totals.items() if d >= since.isoformat())
        if limit:
            pct = used / limit * 100
            flag = "🚨" if pct >= 100 else "⚠️" if pct >= warn else "✅"
            warned |= pct >= warn
            lines.append(f"{flag} {name}: {fmt(used)} / {fmt(limit)} ({pct:.1f}%)")
            lines.append(f"    {bar(pct)} 잔량 {fmt(max(limit - used, 0))}")
        else:
            lines.append(f"• {name}: {fmt(used)} 사용 (한도 미설정)")
    return "\n".join(lines), warned


def send_telegram(token, chat_id, text):
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    http_json(urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data))


def main():
    dry = env_bool("DRY_RUN", False)
    admin_key = os.environ.get("ANTHROPIC_ADMIN_KEY")
    if not admin_key:
        sys.exit("ANTHROPIC_ADMIN_KEY 가 필요합니다.")
    now = datetime.now(KST)
    # 월 시작과 주 시작 중 더 이른 날부터 조회 (UTC 기준 일 버킷)
    start = (now.date().replace(day=1) - timedelta(days=7))
    start = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc) + timedelta(days=1)
    end = datetime(end.year, end.month, end.day, tzinfo=timezone.utc)

    totals = fetch_daily_tokens(admin_key, start, end)
    limits = {"일간": env_int("LIMIT_DAILY"), "주간": env_int("LIMIT_WEEKLY"), "월간": env_int("LIMIT_MONTHLY")}
    msg, warned = build_message(totals, limits, float(os.environ.get("WARN_PERCENT", 80)), now)
    print(msg)

    if dry:
        return
    if not (warned or env_bool("ALWAYS_NOTIFY", True)):
        print("경고 조건 없음 - 발송 생략")
        return
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        sys.exit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 가 필요합니다.")
    send_telegram(token, chat, msg)
    print("Telegram 발송 완료")


if __name__ == "__main__":
    main()
