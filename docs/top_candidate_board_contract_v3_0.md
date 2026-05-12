# Top Candidate Board Contract v3.0

## 목적

v2.8/v2.9에서 확정된 SuperTrend 실시간 후보 산출 결과를 VB.NET Top Candidate Board 화면에서 안정적으로 조회하기 위한 SQL/API 계약 문서입니다.

이 문서는 전략 산출 로직을 추가로 변경하지 않고, 화면이 읽어야 할 조회 레이어와 컬럼 의미를 고정합니다.

## 기준 산출물

v3.0 화면 바인딩의 기준 테이블은 v2.9 산출물입니다.

| Layer | Table | 용도 |
|---|---|---|
| RAW | `supertrend_top_candidate_board_raw_view_v2_9` | 검증용 전체 후보 표시. v2.8의 69개 후보 전체 보존. |
| DEDUP | `supertrend_top_candidate_board_dedup_view_v2_9` | 실전 화면용. 동일 종목 중 최상위 1개만 표시. |
| SUMMARY | `supertrend_top_candidate_board_summary_v2_9` | 보드 레이어/action별 집계 확인. |
| EXAMPLES | `supertrend_top_candidate_board_examples_v2_9` | 미리보기/검증 샘플. |

## 화면 모드

Top Candidate Board는 아래 5개 모드를 기준으로 조회합니다.

| UI Mode | Source Layer | WHERE 조건 | 설명 |
|---|---|---|---|
| `LIVE_COMPACT` | DEDUP | `ui_live_compact_flag_v2_9 = 1` | 실전 압축 화면. AUTO_BUY_READY + WATCH_HOGA_TICK. |
| `TEST_ALL` | RAW | `ui_test_all_flag_v2_9 = 1` | 테스트/검증 화면. REJECT 포함 전체 후보. |
| `AUTO_BUY_ONLY` | DEDUP | `ui_auto_buy_only_flag_v2_9 = 1` | 즉시 매수 가능 후보만 표시. |
| `WATCH_ONLY` | DEDUP | `ui_watch_only_flag_v2_9 = 1` | 호가/틱 재확인 감시 후보만 표시. |
| `REJECT_ONLY` | RAW | `ui_reject_only_flag_v2_9 = 1` | 탈락 후보 검증용. |

## 표준 조회 SQL

### 1. 실전 압축 화면

```sql
SELECT *
FROM supertrend_top_candidate_board_dedup_view_v2_9
WHERE ui_live_compact_flag_v2_9 = 1
ORDER BY dedup_final_rank_no_v2_9 ASC;
```

### 2. 테스트 기간 검증용 전체 후보 화면

```sql
SELECT *
FROM supertrend_top_candidate_board_raw_view_v2_9
WHERE ui_test_all_flag_v2_9 = 1
ORDER BY final_rank_no_v2_8 ASC;
```

### 3. 즉시 매수 후보만 보기

```sql
SELECT *
FROM supertrend_top_candidate_board_dedup_view_v2_9
WHERE ui_auto_buy_only_flag_v2_9 = 1
ORDER BY dedup_final_rank_no_v2_9 ASC;
```

### 4. 호가/틱 감시 후보만 보기

```sql
SELECT *
FROM supertrend_top_candidate_board_dedup_view_v2_9
WHERE ui_watch_only_flag_v2_9 = 1
ORDER BY dedup_final_rank_no_v2_9 ASC;
```

### 5. 탈락 후보 검증용 보기

```sql
SELECT *
FROM supertrend_top_candidate_board_raw_view_v2_9
WHERE ui_reject_only_flag_v2_9 = 1
ORDER BY final_rank_no_v2_8 ASC;
```

## VB.NET 화면 컬럼 권장 순서

| Display | DB Column | 설명 |
|---|---|---|
| 순위 | `dedup_final_rank_no_v2_9` 또는 `final_rank_no_v2_8` | DEDUP은 dedup 순위, RAW는 원본 순위. |
| 액션 | `board_action_v2_8` | `AUTO_BUY_READY`, `WATCH_HOGA_TICK`, `REJECT`. |
| 한글액션 | `board_action_kr_v2_8` | 화면 표시용 한글 라벨. |
| 종목코드 | `code` | 6자리 종목코드. |
| 종목명 | `name` | 종목명. |
| 라벨 | `ticker_label` | 종목 표시 라벨. |
| 진입시간 | `entry_time_text` | 화면 표시용 진입시간. |
| 진입가 | `entry_price` | 후보 기준 진입가. |
| 기대수익률 | `expected_return_pct` | 사후 추정 최대 기대 수익률. |
| MAE위험 | `mae_risk_pct` | 진입 후 최대 역행 위험. |
| 누적거래대금억 | `start_cum_amount_eok` | 시작 시점 누적 거래대금 억 단위. |
| 틱확정점수 | `tick_confirm_score_v2_6` | 호가/틱 확정 점수. |
| 틱강도 | `tick_intensity_v2_6` | 실시간 틱 강도. |
| 매수틱비율 | `buy_tick_ratio_v2_6` | 매수 우위 틱 비율. |
| 대량체결억 | `large_trade_amount_eok_v2_6` | 대량 체결 금액 억 단위. |
| 매수호가압력 | `hoga_bid_pressure_v2_6` | 매수호가 압력. |
| 매도흡수 | `hoga_ask_absorption_v2_6` | 매도호가 흡수. |
| 스프레드위험 | `spread_risk_v2_6` | 스프레드 리스크. |
| 다음행동 | `final_next_action_v2_8` | UI/매매 보조 행동. |
| 사유 | `board_reason_v2_8` | 판정 사유. |
| 실시간스냅샷 | `realtime_snapshot_time` | 실시간 검증 스냅샷 시각. |
| 소스 | `realtime_source_tag` | 실시간 데이터 소스 태그. |

## VB.NET 조회 함수 설계 기준

화면은 `mode`만 받아 SQL을 선택합니다. SQL 문자열은 화면 곳곳에 흩어놓지 않고 단일 함수에서만 반환합니다.

```vbnet
Private Function BuildTopCandidateBoardSql(ByVal mode As String) As String
    Select Case mode
        Case "LIVE_COMPACT"
            Return "SELECT * FROM supertrend_top_candidate_board_dedup_view_v2_9 WHERE ui_live_compact_flag_v2_9 = 1 ORDER BY dedup_final_rank_no_v2_9 ASC"
        Case "TEST_ALL"
            Return "SELECT * FROM supertrend_top_candidate_board_raw_view_v2_9 WHERE ui_test_all_flag_v2_9 = 1 ORDER BY final_rank_no_v2_8 ASC"
        Case "AUTO_BUY_ONLY"
            Return "SELECT * FROM supertrend_top_candidate_board_dedup_view_v2_9 WHERE ui_auto_buy_only_flag_v2_9 = 1 ORDER BY dedup_final_rank_no_v2_9 ASC"
        Case "WATCH_ONLY"
            Return "SELECT * FROM supertrend_top_candidate_board_dedup_view_v2_9 WHERE ui_watch_only_flag_v2_9 = 1 ORDER BY dedup_final_rank_no_v2_9 ASC"
        Case "REJECT_ONLY"
            Return "SELECT * FROM supertrend_top_candidate_board_raw_view_v2_9 WHERE ui_reject_only_flag_v2_9 = 1 ORDER BY final_rank_no_v2_8 ASC"
        Case Else
            Return "SELECT * FROM supertrend_top_candidate_board_dedup_view_v2_9 WHERE ui_live_compact_flag_v2_9 = 1 ORDER BY dedup_final_rank_no_v2_9 ASC"
    End Select
End Function
```

## 검증 기준

v3.0 조회 계약은 아래 조건을 만족해야 합니다.

1. `LIVE_COMPACT`는 DEDUP 레이어에서 조회한다.
2. `TEST_ALL`은 RAW 레이어에서 조회한다.
3. `WATCH_HOGA_TICK`은 실전 압축 화면에 포함된다.
4. `REJECT`는 실전 압축 화면에는 표시하지 않고 검증 화면에서만 표시한다.
5. 화면은 SQL을 직접 조합하지 않고 `mode` 기반으로만 전환한다.
6. 이후 실시간 호가/틱 업데이트는 같은 `code`를 기준으로 현재 보드 행에 덮어쓴다.

## 다음 단계

v3.1에서는 실제 VB.NET 화면 구현에 들어갑니다.

- `frmTopCandidateBoard` 생성
- 모드 콤보박스: `LIVE_COMPACT`, `TEST_ALL`, `AUTO_BUY_ONLY`, `WATCH_ONLY`, `REJECT_ONLY`
- 새로고침 버튼
- DataGridView 바인딩
- 액션별 행 색상 규칙
- 더블클릭 시 종목코드 전달 이벤트
