# Top Candidate Board UI v3.1

## 목적

v3.1은 v2.9/v3.0에서 고정한 Top Candidate Board SQL 계약을 VB.NET 화면으로 연결하기 위한 1차 UI 골격입니다.

전략 산출 로직은 더 변경하지 않고, 다음 두 레이어를 화면 모드로 선택해 조회합니다.

- 실전 화면: `supertrend_top_candidate_board_dedup_view_v2_9`
- 테스트 검증 화면: `supertrend_top_candidate_board_raw_view_v2_9`

## 생성 파일

| 파일 | 설명 |
|---|---|
| `vbnet/frmTopCandidateBoard.vb` | VB.NET WinForms 독립 폼. 콤보/새로고침/DataGridView/더블클릭 이벤트 포함. |
| `scripts/build_top_candidate_board_ui_v3_1.ps1` | 로컬 검증용 실행 스크립트. 파일 존재/핵심 문자열/SQL 계약을 확인합니다. |
| `docs/top_candidate_board_ui_v3_1.md` | 현재 문서. |

## 화면 기능

1. 모드 콤보박스
   - `LIVE_COMPACT`
   - `TEST_ALL`
   - `AUTO_BUY_ONLY`
   - `WATCH_ONLY`
   - `REJECT_ONLY`

2. 새로고침 버튼
   - 현재 선택된 모드의 SQL을 실행합니다.
   - 결과를 DataGridView에 바인딩합니다.

3. DataGridView 표시 컬럼
   - 순위
   - 액션
   - 한글액션
   - 종목코드
   - 종목명
   - 라벨
   - 진입시간
   - 진입가
   - 기대수익률
   - MAE위험
   - 누적거래대금억
   - 틱확정점수
   - 틱강도
   - 매수틱비율
   - 대량체결억
   - 매수호가압력
   - 매도흡수
   - 스프레드위험
   - 다음행동
   - 사유
   - 실시간스냅샷
   - 소스

4. 행 색상 규칙
   - `AUTO_BUY_READY`: 매수 준비 후보 강조
   - `WATCH_HOGA_TICK`: 호가/틱 확인 후보 강조
   - `REJECT`: 검증용 탈락 후보 약하게 표시

5. 더블클릭 이벤트
   - 행 더블클릭 시 `CandidateActivated(code, name)` 이벤트를 발생시킵니다.
   - MainForm, ChartBoard, 실시간 호가창, 차트창과 후속 연결할 수 있습니다.

## 연결 방식

### 생성자에 연결문자열 전달

```vbnet
Dim f As New frmTopCandidateBoard(mysqlConnectionString)
AddHandler f.CandidateActivated, AddressOf OnCandidateActivated
f.Show()
```

### 환경변수 사용

생성자에 연결문자열을 전달하지 않으면 `MYSQL_CONN` 환경변수를 읽습니다.

```vbnet
Dim f As New frmTopCandidateBoard()
f.Show()
```

## 기준 SQL

### LIVE_COMPACT

```sql
SELECT ...
FROM supertrend_top_candidate_board_dedup_view_v2_9
WHERE ui_live_compact_flag_v2_9 = 1
ORDER BY dedup_final_rank_no_v2_9 ASC;
```

### TEST_ALL

```sql
SELECT ...
FROM supertrend_top_candidate_board_raw_view_v2_9
WHERE ui_test_all_flag_v2_9 = 1
ORDER BY final_rank_no_v2_8 ASC;
```

## v3.2 다음 단계

v3.2에서는 현재 독립 폼을 실제 프로젝트 Shell에 연결합니다.

1. MainForm 메뉴/버튼에서 `frmTopCandidateBoard` 열기
2. `CandidateActivated` 이벤트를 ChartBoard 또는 종목 상세창으로 연결
3. 현재 선택 종목의 실시간 호가/틱 업데이트를 해당 행에 덮어쓰기
4. `WATCH_HOGA_TICK` 후보를 테스트 기간에는 전체 표시, 실전에서는 압축 표시로 전환
