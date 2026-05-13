# Top Candidate Board Integration v3.2

## 목적

v3.2는 v3.1에서 만든 `frmTopCandidateBoard` 독립 화면을 기존 VB.NET MainForm, ChartBoard, 종목 상세창과 연결하기 위한 통합 가이드 단계입니다.

현재 단계에서는 기존 프로젝트 파일을 직접 수정하지 않고, 붙여 넣을 수 있는 강타입 샘플 코드를 별도 파일로 제공합니다.

## 생성 파일

| 파일 | 설명 |
|---|---|
| `vbnet/TopCandidateBoardIntegrationGuide.vb` | MainForm에 연결할 샘플 코드. 메뉴/버튼 이벤트, 폼 인스턴스 관리, 더블클릭 이벤트 수신 포함. |
| `scripts/build_top_candidate_board_integration_v3_2.ps1` | v3.2 파일 존재 및 핵심 토큰 검증 스크립트. |
| `docs/top_candidate_board_integration_v3_2.md` | 현재 문서. |

## 통합 원칙

1. `frmTopCandidateBoard`는 독립 폼으로 유지합니다.
2. MainForm은 `frmTopCandidateBoard`를 1개만 열고 재사용합니다.
3. 종목 더블클릭은 `CandidateActivated(code, name)` 이벤트로 전달합니다.
4. ChartBoard나 종목 상세창 연결은 MainForm 쪽의 기존 함수명에 맞춰 1곳에서만 처리합니다.
5. 실시간 호가/틱 업데이트는 다음 단계에서 code 기준으로 현재 행에 덮어쓰는 방식으로 확장합니다.

## MainForm 연결 흐름

```text
MainForm 버튼/메뉴 클릭
    ↓
OpenTopCandidateBoard()
    ↓
frmTopCandidateBoard 생성 또는 기존 창 Activate
    ↓
사용자가 행 더블클릭
    ↓
OnTopCandidateActivated(code, name)
    ↓
차트/상세/호가 화면 열기
```

## MainForm에 추가할 필드

```vbnet
Private _topCandidateBoardForm As frmTopCandidateBoard
```

## MainForm에 추가할 버튼/메뉴 이벤트 예시

```vbnet
Private Sub btnTopCandidateBoard_Click(ByVal sender As Object, ByVal e As EventArgs)
    OpenTopCandidateBoard()
End Sub
```

## 연결 함수 예시

```vbnet
Private Sub OpenTopCandidateBoard()
    If _topCandidateBoardForm IsNot Nothing AndAlso Not _topCandidateBoardForm.IsDisposed Then
        _topCandidateBoardForm.Activate()
        Return
    End If

    _topCandidateBoardForm = New frmTopCandidateBoard(GetMysqlConnectionString())
    AddHandler _topCandidateBoardForm.CandidateActivated, AddressOf OnTopCandidateActivated
    _topCandidateBoardForm.Show(Me)
End Sub
```

## 더블클릭 수신 예시

```vbnet
Private Sub OnTopCandidateActivated(ByVal code As String, ByVal name As String)
    OpenChartForCandidate(code, name)
End Sub
```

## 연결문자열 기준

프로젝트가 이미 `MYSQL_CONN` 환경변수를 사용하면 다음처럼 간단히 연결할 수 있습니다.

```vbnet
Private Function GetMysqlConnectionString() As String
    Dim value As String = Environment.GetEnvironmentVariable("MYSQL_CONN")
    If value Is Nothing Then
        Return String.Empty
    End If
    Return value.Trim()
End Function
```

프로젝트 내부 DB Helper가 있으면 `GetMysqlConnectionString()` 내부만 기존 함수로 바꾸면 됩니다.

## v3.2 검증 기준

1. `frmTopCandidateBoard.vb`가 존재해야 합니다.
2. `TopCandidateBoardIntegrationGuide.vb`가 존재해야 합니다.
3. Integration Guide에는 다음 토큰이 포함되어야 합니다.
   - `OpenTopCandidateBoard`
   - `OnTopCandidateActivated`
   - `CandidateActivated`
   - `frmTopCandidateBoard`
   - `GetMysqlConnectionString`
4. 서버/로컬 동기화는 `git pull → 실행 → git status clean` 흐름을 유지합니다.

## v3.3 다음 단계

v3.3에서는 실제 프로젝트 구조에 맞춰 다음 중 하나를 선택합니다.

1. MainForm에 직접 메뉴/버튼 추가
2. MDI/Docking Shell에 ToolWindow로 등록
3. ChartBoard와 직접 연결
4. 실시간 호가/틱 Snapshot 업데이트를 code 기준으로 DataGridView 행에 반영
