# Korea Data Suite

[English](README.md) | **한국어**

한국 공공데이터를 위한 깔끔하고 개발자 친화적인 REST API 모음.
한국 정부 공공데이터는 강력하지만 소비하기 어렵습니다 — 한국어 전용 문서,
XML 응답, 레거시 인증. 이 스위트는 그것을 단순한 JSON API로 정규화합니다.

## API 목록

| API | 상태 | 설명 |
|-----|--------|-------------|
| 공휴일 & 영업일 | ✅ v1 | 한국 공휴일(대체공휴일·임시공휴일 포함)과 영업일 계산 |
| 부동산 실거래가 | ✅ v1 | 정규화된 국토교통부(MOLIT) 실거래가 (아파트/오피스텔/토지, 매매 & 임대) — 전국 261개 시군구 |
| 주소 툴킷 | 🚧 계획 | 도로명/지번 주소 변환, 로마자 표기 |
| 사업자등록 | 🚧 계획 | 사업자등록번호(BRN) 검증 & 보강 |

## 빠른 시작 (셀프 호스팅)

```bash
uv sync
uv run uvicorn app.main:app --port 8642
curl "http://127.0.0.1:8642/v1/health"
```

## 공휴일 & 영업일 API

```bash
# 연도(또는 월)의 모든 공휴일
curl "http://127.0.0.1:8642/v1/holidays?year=2026" -H "X-API-Key: <key>"

# 특정 날짜가 공휴일/영업일인지 확인
curl "http://127.0.0.1:8642/v1/holidays/check?date=2026-03-02" -H "X-API-Key: <key>"

# N 영업일 더하기 (주말·공휴일 건너뜀)
curl "http://127.0.0.1:8642/v1/business-days/add?date=2026-12-31&days=1" -H "X-API-Key: <key>"

# 기간 내 영업일 수 세기 (양끝 포함)
curl "http://127.0.0.1:8642/v1/business-days/count?start=2026-09-21&end=2026-09-27" -H "X-API-Key: <key>"
```

법정 공휴일은 물론 **대체공휴일**, **임시공휴일**, 선거일까지 커버합니다 —
글로벌 공휴일 API들이 한국에 대해 가장 자주 틀리는 케이스들입니다.

## 부동산 실거래가 API

정규화된 국토교통부 실거래가 — 아파트, 오피스텔, 토지; 매매, 전세, 월세 —
를 커서 페이지네이션이 있는 깔끔한 영문 JSON으로 제공합니다.

```bash
# 실거래가 (강남구 아파트 매매)
curl "http://127.0.0.1:8642/v1/realestate/transactions?region=11680&property_type=apartment&trade_type=sale" -H "X-API-Key: <key>"

# 날짜 범위 필터 + 반환된 커서로 페이지네이션
curl "http://127.0.0.1:8642/v1/realestate/transactions?region=11680&date_from=2026-01-01&limit=50&cursor=<next_cursor>" -H "X-API-Key: <key>"

# 지역 코드 (법정동 LAWD 5자리)
curl "http://127.0.0.1:8642/v1/realestate/regions" -H "X-API-Key: <key>"
```

일간 동기화는 당월 + 전월을 수집합니다. 과거 이력은 백필 CLI를 사용하세요:

```bash
uv run python scripts/backfill.py --from 2025-01 --to 2025-12 --regions 11680,11650
```

## 설정

환경변수 (접두사 `KDS_`, `.env` 지원):

| 변수 | 기본값 | 설명 |
|----------|---------|-------------|
| `KDS_DEV_MODE` | `false` | API 키 인증 건너뛰기 (로컬 개발용) |
| `KDS_API_KEYS` | — | 허용할 API 키 목록 (콤마 구분) |
| `KDS_PROXY_SECRETS` | — | 마켓플레이스 프록시 시크릿 목록 (콤마 구분) |
| `KDS_DB_PATH` | `data/kds.db` | SQLite 경로 |
| `KDS_DATA_GO_KR_KEY` | — | data.go.kr 서비스 키 (선택; 공휴일 + 실거래가 동기화 활성화) |
| `KDS_ENABLE_SCHEDULER` | `true` | 공휴일(주간) + 실거래가(일간) 동기화 스케줄러 |
| `KDS_RE_REGIONS` | 전국 261개 시군구 전체 | 동기화할 LAWD 코드 (부분 지정 오버라이드, 콤마 구분) |
| `KDS_RE_DATASETS` | 전체 | 데이터셋 키 (apt_trade, apt_rent, offi_trade, offi_rent, land_trade — 콤마 구분) |

## 데이터 출처 & 저작권 표시

- 공휴일 데이터: 한국천문연구원(KASI) 특일정보,
  [공공데이터포털 (data.go.kr)](https://www.data.go.kr/) 경유 — KOGL 제1유형.
  번들 시드 데이터(2025–2027) 포함; 서비스 키 설정 시 주간 갱신.
- 실거래가 데이터: 국토교통부 실거래가 공개시스템,
  [공공데이터포털 (data.go.kr)](https://www.data.go.kr/) 경유 — KOGL 제1유형.

## 데몬으로 실행 (macOS)

```bash
# 설치 & 시작 (크래시 시 자동 재시작, 로그인 시 시작)
./scripts/install-daemon.sh

# Cloudflare Tunnel과 함께 (최초 1회 `cloudflared tunnel login/create` 후)
./scripts/install-daemon.sh --with-tunnel

# 로그
tail -f ~/Library/Logs/kds/api.out.log

# 제거
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.choiyounggi.kds-api.plist
rm ~/Library/LaunchAgents/com.choiyounggi.kds-api.plist
```

서빙을 위해 머신을 깨어 있게 하려면 시스템 잠자기를 비활성화하거나
(`sudo pmset -a sleep 0`) 상시 켜져 있는 전용 머신을 사용하세요.
포트를 열지 않고 Cloudflare Tunnel로 API를 노출하는 방법은
`deploy/cloudflared.example.yml`을 참고하세요.

### 동시 트래픽 처리

읽기 경로와 쓰기 경로가 분리되어 있어 트래픽이 독립적으로 확장됩니다:

- **SQLite WAL 모드** (초기화 시 1회 설정) + `busy_timeout` — 리더가 일간
  라이터를 막지 않고 그 반대도 마찬가지이며, 여러 읽기 워커가 동시에 돌 수
  있습니다.
- **API 프로세스는 읽기 전용, 멀티 워커.** `scripts/run.sh`는 uvicorn을
  `--workers ${KDS_WORKERS:-2}` + `KDS_ENABLE_SCHEDULER=false`로 띄웁니다.
  각 워커는 별도 프로세스(별도 GIL)이고, WAL 덕에 전부 동시에 읽습니다.
  코어 수에 맞춰 `KDS_WORKERS`를 올려 읽기를 확장하세요.
- **일간 수집은 자체 프로세스로 실행** (`com.choiyounggi.kds-sync`, 04:00,
  `scripts/sync.py`) — API 서버 안에서 돌지 않으므로, 수천 행 배치가 요청
  처리와 GIL을 두고 경쟁하는 일이 없습니다.
- **엣지 캐싱** (선택): 응답은 보안을 위해 `Cache-Control: no-store`를
  달고 나갑니다. 실거래가 데이터는 공개 데이터이고 기껏해야 하루 단위로
  바뀌므로 — 오리진 부하가 커지면 짧은 `Cache-Control: public, max-age=...`로
  서빙하고 CDN이 읽기를 흡수하게 하세요.

### 외부 노출 전 보안 체크리스트

앱은 코드 레이어에서 하드닝되어 있습니다(API 키 인증 fail-closed, 파라미터
바인딩 SQL, 엄격한 입력 검증, 5xx 포함 모든 응답의 보안 헤더, docs/스키마
기본 비활성, 새니타이즈된 에러). 다음은 터널을 열기 전에 갖춰야 하는
**엣지/배포 책임**입니다:

- **프로덕션에서 절대 `KDS_DEV_MODE=true`를 설정하지 마세요** — 모든 인증이
  꺼집니다. 켜져 있으면 앱이 시작 시 경고를 로깅합니다.
- 터널 호스트네임에 **Cloudflare rate limiting + WAF** — 앱에는 설계상
  앱 레이어 rate limit이 없습니다(엣지 책임).
- **HSTS + TLS**는 Cloudflare 엣지에서 종단됩니다. 엣지에서 HSTS가 켜져
  있는지 확인하세요(오리진은 `127.0.0.1`에서 평문 HTTP만 서빙).
- 프로덕션에서는 `KDS_ENABLE_DOCS`를 설정하지 않거나 `false`로 두세요.
  오리진에서 `/docs` `/openapi.json`을 서빙할 때만 `true`로.

## SEO 마케팅 사이트 (프로그래매틱)

정적 SEO 최적화 마케팅 사이트가 `scripts/gen_site.py`에 의해 **라이브 DB로부터**
생성됩니다. 실거래 데이터가 있는 모든 지역에 대해 한국어 랜딩 페이지(사용자가
실제로 검색하는 쿼리 — "강남구 아파트 실거래가 API" — 를 실제 MOLIT 통계,
동작하는 `curl` 예시, 가입 CTA로 뒷받침)를 만들고, 공휴일 필러 페이지, 홈,
`sitemap.xml`, `robots.txt`까지 냅니다.

**품질 게이트 (중요):** 아파트 매매 행이 최소 `MIN_SALE_ROWS`(30)개 이상인
지역만 게시됩니다. 데이터가 부족한 지역은 건너뜁니다 — 검색엔진이 페널티를
주는 얇은/도어웨이 페이지를 의도적으로 피하는 것입니다.

```bash
# site/dist로 생성 (data/kds.db를 읽음)
uv run python scripts/gen_site.py --out site/dist
```

설정은 env 기반이라 같은 생성기가 어떤 도메인에도 동작합니다
(`deploy/site.env`에 넣으세요 — gitignore 대상, `deploy/site.env.example` 복사):

| Env | 의미 |
|-----|-----|
| `KDS_SITE_URL` | canonical/sitemap 베이스, 예: `https://korea-data.cloud` |
| `KDS_API_ORIGIN` | 페이지 내 `curl` 예시에 표시되는 오리진, 예: `https://api.korea-data.cloud` |
| `KDS_CTA_URL` | 가입 call-to-action (RapidAPI / Zyla / Postman 리스팅) |
| `KDS_SITE_DIR` | 앱이 서빙하는 출력 디렉토리 (기본 `site/dist`) |

### 서빙 — API 앱이 함께 서빙

FastAPI 앱이 **모든 비-API 경로**에서 `site/dist`를 서빙하고(`app.mount("/")`),
`/v1/*`는 JSON API로 남습니다. 둘은 서로 다른 응답 헤더를 받습니다: API는
잠긴 `default-src 'none'` CSP + `no-store`를 유지하고, 사이트는 HTML 렌더링
가능한 CSP(`script-src 'none'`, 인라인 스타일 허용) + `public` 캐시를 받습니다.
파일은 요청마다 디스크에서 읽으므로 **사이트를 재생성하면 앱 재시작 없이 바로
반영됩니다** — 재시작이 필요한 건 코드 변경뿐입니다.

사이트는 **API와 같은 호스트**(`api.korea-data.cloud`)에서 서빙됩니다 — API는
`/v1` 아래, 사이트는 그 외 전부 — 그래서 새 터널 호스트네임이나 DNS가 필요
없습니다. 서빙 호스트에서 1회:

```bash
cp deploy/site.env.example deploy/site.env    # KDS_SITE_URL == KDS_API_ORIGIN == https://api.korea-data.cloud
uv run python scripts/gen_site.py --out site/dist   # 1회 생성
# 이 통합(새 코드)이 반영되도록 API 앱을 재시작 — 이후 사이트는
# https://api.korea-data.cloud/ , /holidays/ , /realestate/... 에서 라이브.
```

Google Search Console에 `https://api.korea-data.cloud/sitemap.xml`을 1회 제출하세요.

> 나중에 사이트를 bare `korea-data.cloud` / `www`에 올리고 싶다면? 그 호스트네임을
> 같은 `http://127.0.0.1:8642`로 보내는 ingress 규칙을 추가하고, DNS를 라우팅하고,
> `KDS_SITE_URL`을 그쪽으로 바꾸세요. 필수는 아닙니다 — SEO에는 지금의 api 호스트로 충분합니다.

> 첫 실행에는 이력이 필요합니다: 일간 동기화는 당월만 수집합니다. 페이지에 실제
> 깊이를 주려면 1회 백필하세요 —
> `uv run python scripts/backfill.py --from 2025-07 --to 2026-06 --regions <codes> --datasets apt_trade,apt_rent`.

### 자동화 (macOS 데몬)

`deploy/com.choiyounggi.kds-site.plist`가 매일 04:30(04:00 동기화 직후)에
`scripts/publish_site.sh`로 사이트를 재생성합니다. 앱이 디스크에서 서빙하므로
갱신된 페이지는 즉시 라이브입니다 — 재시작도, 외부 배포도 없습니다:

```bash
cp deploy/com.choiyounggi.kds-site.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.choiyounggi.kds-site.plist
tail -f ~/Library/Logs/kds/site.out.log
```

> 가동시간 참고: 사이트는 CDN이 아니라 로컬 앱이 서빙하므로 SEO 가용성은 머신을
> 따라갑니다 — 서빙을 위해 깨어 있게 유지하세요(API가 이미 요구하는 `pmset`).
> 나중에 상시 호스팅이 필요하면 같은 `site/dist`를 Cloudflare Pages로 밀어도 됩니다.

## MCP 서버 (AI 에이전트 접근)

이 API는 독립형 [Model Context Protocol](https://modelcontextprotocol.io)
서버로도 패키징되어 있습니다 — [`packages/korea-data-mcp/`](./packages/korea-data-mcp) —
AI 에이전트(Claude Desktop/Code, Cursor, …)가 엔드포인트를 직접 발견하고 호출할
수 있습니다. 자체 최소 패키지(의존성: `mcp`, `httpx`)이며, PyPI 게시 / MCP
Registry 등록 대상이 되는 것도 이 패키지입니다.

빠른 추가 (PyPI 게시 전, 이 레포에서 바로 — 키는 각자 준비):

```bash
claude mcp add korea-data-suite --env KDS_API_KEY=<key> \
  -- uvx --from "git+https://github.com/choiyounggi/korea-data-suite#subdirectory=packages/korea-data-mcp" korea-data-mcp
```

도구 목록, 클라이언트 설정, (PyPI 게시 후) `uvx korea-data-mcp` 사용법은
[`packages/korea-data-mcp/README.md`](./packages/korea-data-mcp/README.md)를 보세요.

## 라이선스

MIT © choiyounggi
