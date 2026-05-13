# Session Handoff - Top Candidate Board / SuperTrend Realtime Candidate Flow

Date: 2026-05-13
Repository: `hoonoh57/Leader_Lab`
Local path: `E:\2026\Leader_Lab`

## 핵심 원칙

이번 세션에서 사용자가 재확인한 가장 중요한 운영 원칙은 다음이다.

```powershell
cd E:\2026\Leader_Lab

git pull origin main

.\scripts\<versioned_script>.ps1

git status
```

- 코드는 서버 GitHub 저장소에서 생성/수정한다.
- 로컬 파일을 즉석 패치하지 않는다.
- 로컬은 `pull -> PowerShell 실행 -> git status` 검증만 수행한다.
- 실패하면 로컬 수정이 아니라 서버 스크립트를 수정하고 다시 pull한다.
- 최종 상태는 항상 `working tree clean`이어야 한다.

## Git safe.directory 이슈

로컬에서 다음 에러가 발생했다.

```text
fatal: detected dubious ownership in repository at 'E:/2026/Leader_Lab'
```

해결 명령:

```powershell
git config --global --add safe.directory E:/2026/Leader_Lab
```

이후 pull/status 정상화됨.

## 완료된 흐름 요약

### v1.3 ST Continuation Entry Discovery

사용자 실행 결과에서 `ST_START_ENTRY`가 평균/중앙값 기준으로 가장 높은 사후 최대수익률을 보였다.

대표 결론:

- `ST_START_ENTRY`, period 7, multiplier 2.0: 평균 약 11.62%, 중앙값 약 10.4%, continuation success 약 55.6%.
- `EARLY3_COMPOSITE_ENTRY`, period 7, multiplier 2.0: 평균 약 3.99%, 중앙값 약 1.48%, continuation success 약 33.0%.
- 결론: 진입 성능은 ST 시작점이 가장 좋지만 실전에서는 호가/틱 확인과 UI 선별이 필요하다.

### v1.5 실패 진단과 MySQL 복구

초기 SQLite 자동 탐색 로직이 잘못 들어가 사용자가 지적했다. 프로젝트 기준은 MySQL이다.

주요 문제:

- SQLite DB 탐색 로직 도입 오류.
- `information_schema` alias 문제로 `table_name`, `column_name` KeyError.
- source table 자동 선택 오류로 detail row_count=0.

결론:

- MySQL 기반 유지.
- source table은 entry_type 전체가 존재하는 테이블을 사용해야 한다.
- 로컬 최신 파일과 서버 상태를 먼저 정상화한 뒤 진행해야 한다.

### v1.6 ~ v2.0 SQL alias/order 문제

반복된 에러:

```text
Column count doesn't match value count at row 1
Unknown column 'avg_execution_score_v1_9' in 'order clause'
Unknown column 'avg_entry_score_v2_0' in 'order clause'
```

교훈:

- summary/order by는 실제 생성 컬럼명을 기준으로 구성한다.
- alias를 같은 SELECT 내부 order by에 무리하게 쓰지 않는다.

### v2.3 ~ v2.7 Hoga/Tick 연결 전 단계

발생한 주요 문제:

- v2.3 required columns missing.
- v2.3 `Data too long for column 'example_scope'`.
- v2.4 PyMySQL `%` format collision.
- v2.5 f-string syntax error.
- v2.7 f-string backslash error.

교훈:

- 복잡한 SQL fragment는 f-string 내부에서 만들지 말고 사전 변수로 조립한다.
- SQL `%`는 PyMySQL parameter formatting과 충돌하지 않도록 escaping한다.
- example/table column length는 넉넉하게 둔다.

### v2.8 Final Board View

사용자 요청: 테스트 기간 검증용으로 Top Candidate Board에 `WATCH_HOGA_TICK` 포함 전체 69개 후보를 선택적으로 표시 가능하게 할 것.

결과:

```text
total_board_rows=69
AUTO_BUY_READY=1
WATCH_HOGA_TICK=8
REJECT=60
compact_visible_rows=9
test_all_candidates_rows=69
```

의미:

- 실전 압축 화면: AUTO_BUY_READY 1 + WATCH_HOGA_TICK 8 = 9개.
- 검증 전체 화면: AUTO_BUY_READY 1 + WATCH_HOGA_TICK 8 + REJECT 60 = 69개.

### v2.9 Top Candidate Board Contract

생성 파일:

```text
scripts/build_supertrend_top_candidate_board_contract_v2_9.py
scripts/build_supertrend_top_candidate_board_contract_v2_9.ps1
```

DB 산출물:

```text
supertrend_top_candidate_board_raw_view_v2_9
supertrend_top_candidate_board_dedup_view_v2_9
supertrend_top_candidate_board_summary_v2_9
supertrend_top_candidate_board_examples_v2_9
```

확인된 결과:

```text
RAW:
  AUTO_BUY_READY   1
  WATCH_HOGA_TICK  8
  REJECT           60
  total            69

DEDUP:
  AUTO_BUY_READY   1
  WATCH_HOGA_TICK  6
  REJECT           54
  total            61
```

기준 SQL:

```sql
SELECT *
FROM supertrend_top_candidate_board_dedup_view_v2_9
WHERE ui_live_compact_flag_v2_9 = 1
ORDER BY dedup_final_rank_no_v2_9 ASC;
```

```sql
SELECT *
FROM supertrend_top_candidate_board_raw_view_v2_9
WHERE ui_test_all_flag_v2_9 = 1
ORDER BY final_rank_no_v2_8 ASC;
```

### v3.0 SQL Contract 문서화

생성 파일:

```text
docs/top_candidate_board_contract_v3_0.md
```

내용:

- v2.9 RAW/DEDUP 기준 조회 계약 고정.
- UI mode 5개 고정: `LIVE_COMPACT`, `TEST_ALL`, `AUTO_BUY_ONLY`, `WATCH_ONLY`, `REJECT_ONLY`.
- VB.NET `BuildTopCandidateBoardSql(mode)` 기준 문서화.

### v3.1 VB.NET Top Candidate Board UI 골격

생성 파일:

```text
docs/top_candidate_board_ui_v3_1.md
vbnet/frmTopCandidateBoard.vb
scripts/build_top_candidate_board_ui_v3_1.ps1
```

`frmTopCandidateBoard.vb` 기능:

- 모드 콤보: `LIVE_COMPACT`, `TEST_ALL`, `AUTO_BUY_ONLY`, `WATCH_ONLY`, `REJECT_ONLY`.
- Refresh 버튼.
- DataGridView 바인딩.
- v2.9 RAW/DEDUP 조회 SQL.
- `AUTO_BUY_READY`, `WATCH_HOGA_TICK`, `REJECT` 행 색상.
- 행 더블클릭 시 `CandidateActivated(code, name)` 이벤트.
- 연결문자열은 생성자 또는 `MYSQL_CONN` 환경변수.

로컬 검증 완료:

```text
=== VERIFY v3.1 Top Candidate Board UI ===
doc= E:\2026\Leader_Lab\docs\top_candidate_board_ui_v3_1.md
form= E:\2026\Leader_Lab\vbnet\frmTopCandidateBoard.vb
form_bytes= 15195
doc_bytes= 3203
modes= LIVE_COMPACT, TEST_ALL, AUTO_BUY_ONLY, WATCH_ONLY, REJECT_ONLY
tables= supertrend_top_candidate_board_dedup_view_v2_9, supertrend_top_candidate_board_raw_view_v2_9
=== DONE scripts/build_top_candidate_board_ui_v3_1.ps1 ===
```

`git status` clean 확인.

### v3.2 MainForm/ChartBoard 연결 가이드

세션 종료 직전 서버에 생성한 파일:

```text
docs/top_candidate_board_integration_v3_2.md
vbnet/TopCandidateBoardIntegrationGuide.vb
scripts/build_top_candidate_board_integration_v3_2.ps1
```

목적:

- 기존 MainForm을 직접 훼손하지 않고, 붙여넣기 가능한 연결 가이드 제공.
- `frmTopCandidateBoard`를 MainForm에서 1개 인스턴스로 열고 재사용.
- `CandidateActivated(code, name)` 이벤트를 ChartBoard/상세창으로 연결.

다음 세션 첫 작업은 v3.2 로컬 pull 및 검증이다.

```powershell
cd E:\2026\Leader_Lab

git pull origin main

.\scripts\build_top_candidate_board_integration_v3_2.ps1

git status
```

예상 성공 출력:

```text
=== VERIFY v3.2 Top Candidate Board Integration ===
doc= E:\2026\Leader_Lab\docs\top_candidate_board_integration_v3_2.md
guide= E:\2026\Leader_Lab\vbnet\TopCandidateBoardIntegrationGuide.vb
form= E:\2026\Leader_Lab\vbnet\frmTopCandidateBoard.vb
integration_tokens= OpenTopCandidateBoard, OnTopCandidateActivated, CandidateActivated, frmTopCandidateBoard
next= v3.3 MainForm actual patch or Docking ToolWindow registration
=== DONE scripts/build_top_candidate_board_integration_v3_2.ps1 ===
```

## 현재 주요 파일

```text
docs/top_candidate_board_contract_v3_0.md
docs/top_candidate_board_ui_v3_1.md
docs/top_candidate_board_integration_v3_2.md
docs/session_handoff_top_candidate_board_2026_05_13.md

todo_list.md

scripts/build_supertrend_top_candidate_board_contract_v2_9.py
scripts/build_supertrend_top_candidate_board_contract_v2_9.ps1
scripts/build_top_candidate_board_ui_v3_1.ps1
scripts/build_top_candidate_board_integration_v3_2.ps1

vbnet/frmTopCandidateBoard.vb
vbnet/TopCandidateBoardIntegrationGuide.vb
```

## 다음 세션 시작 명령

```powershell
cd E:\2026\Leader_Lab

git pull origin main

.\scripts\build_top_candidate_board_integration_v3_2.ps1

git status
```

## v3.3 후보 작업

v3.3은 실제 프로젝트 연결 단계다. 선택지는 두 가지다.

### A. MainForm 직접 연결

- MainForm 메뉴/버튼 추가.
- `OpenTopCandidateBoard()` 실제 추가.
- `CandidateActivated` 이벤트를 기존 차트 열기 함수와 연결.
- `.vbproj`에 `frmTopCandidateBoard.vb` 포함.

### B. Docking/ToolWindow 연결

- WeifenLuo DockPanel 또는 현재 MDI Shell에 ToolWindow 등록.
- Top Candidate Board와 ChartBoard를 나란히 배치.
- 후보 더블클릭 시 ChartBoard 종목 전환.

사용자 UI 선호상 최종형은 B가 적합하지만, 안정성 우선이면 A로 먼저 작동 확인 후 B로 확장한다.

## 다음 세션 주의 사항

- 로컬 파일 즉석 수정 금지.
- 서버 구현/검증 스크립트 생성 후 로컬 pull/실행.
- MySQL 유지, SQLite 재도입 금지.
- VB.NET 규칙 유지: `Option Strict On`, `Option Explicit On`, `Option Infer Off`, 모든 변수 타입 명시.
- SQL alias/order by 문제는 실제 생성 컬럼명 기준으로 검증.
