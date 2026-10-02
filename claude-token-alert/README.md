# Claude 토큰 잔량 Telegram 알림

일간/주간/월간 토큰 사용량과 잔량(설정한 한도 기준)을 Telegram으로 보냅니다.
GitHub Actions에서 하루 2회(09:00, 18:00 KST) 자동 실행되므로 **로컬 설치/저장소가 필요 없습니다.**

## 설정 (GitHub 저장소 → Settings → Secrets and variables → Actions)

**Secrets**
| 이름 | 설명 |
|---|---|
| `ANTHROPIC_ADMIN_KEY` | Console → Settings → Admin keys 에서 발급한 `sk-ant-admin...` 키 (조직 계정 필요) |
| `TELEGRAM_BOT_TOKEN` | Telegram `@BotFather` → `/newbot` 으로 발급 |
| `TELEGRAM_CHAT_ID` | 봇에게 메시지를 보낸 뒤 `https://api.telegram.org/bot<TOKEN>/getUpdates` 의 `chat.id` |

**Variables** (선택, 토큰 단위)
`LIMIT_DAILY`, `LIMIT_WEEKLY`, `LIMIT_MONTHLY`, `WARN_PERCENT`(기본 80)

실행: Actions 탭 → *Claude Token Alert* → *Run workflow*

## 로컬 테스트 (발송 없이)
```
ANTHROPIC_ADMIN_KEY=sk-ant-admin... LIMIT_DAILY=1000000 DRY_RUN=true python3 claude-token-alert/token_alert.py
```

## 참고 / 한계
- Anthropic은 "남은 토큰"을 직접 제공하지 않아, **사용량(Usage API) − 직접 정한 한도**로 잔량을 계산합니다.
- Claude.ai/Claude Code 구독의 5시간·주간 한도는 공개 API가 없어 조회할 수 없습니다. (API/Console 조직 사용량만 해당)
- 주간은 월요일 시작, 일 단위 집계는 UTC 기준입니다.
