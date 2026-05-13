Option Strict On
Option Explicit On
Option Infer Off

Imports System
Imports System.Windows.Forms

' =============================================================================
' TopCandidateBoardIntegrationGuide v3.2
' =============================================================================
' 이 파일은 기존 MainForm을 직접 수정하지 않고, MainForm에 붙일 연결 코드를
' 안전하게 분리한 가이드 파일입니다.
'
' 사용 방법:
' 1. frmTopCandidateBoard.vb를 프로젝트에 포함합니다.
' 2. MainForm에 아래 Region 내부 코드를 옮겨 붙입니다.
' 3. 기존 메뉴/버튼 클릭 이벤트에서 OpenTopCandidateBoard()를 호출합니다.
' 4. OnTopCandidateActivated(code, name) 내부를 기존 차트/상세창 함수명에 맞춥니다.
' =============================================================================

Public NotInheritable Class TopCandidateBoardIntegrationGuide
    Private Sub New()
    End Sub
End Class

' =============================================================================
' MainForm에 추가할 코드 시작
' =============================================================================
'
'Private _topCandidateBoardForm As frmTopCandidateBoard
'
'Private Sub btnTopCandidateBoard_Click(ByVal sender As Object, ByVal e As EventArgs)
'    OpenTopCandidateBoard()
'End Sub
'
'Private Sub menuTopCandidateBoard_Click(ByVal sender As Object, ByVal e As EventArgs)
'    OpenTopCandidateBoard()
'End Sub
'
'Private Sub OpenTopCandidateBoard()
'    If _topCandidateBoardForm IsNot Nothing AndAlso Not _topCandidateBoardForm.IsDisposed Then
'        _topCandidateBoardForm.Activate()
'        Return
'    End If
'
'    _topCandidateBoardForm = New frmTopCandidateBoard(GetMysqlConnectionString())
'    AddHandler _topCandidateBoardForm.CandidateActivated, AddressOf OnTopCandidateActivated
'    _topCandidateBoardForm.Show(Me)
'End Sub
'
'Private Function GetMysqlConnectionString() As String
'    Dim value As String = Environment.GetEnvironmentVariable("MYSQL_CONN")
'    If value Is Nothing Then
'        Return String.Empty
'    End If
'    Return value.Trim()
'End Function
'
'Private Sub OnTopCandidateActivated(ByVal code As String, ByVal name As String)
'    If String.IsNullOrWhiteSpace(code) Then
'        Return
'    End If
'
'    ' TODO: 기존 프로젝트 함수명에 맞춰 아래 1개만 활성화합니다.
'    ' OpenChartForCandidate(code, name)
'    ' OpenChart(code)
'    ' ShowTickerDetail(code, name)
'    ' ChartBoard.OpenTicker(code, name)
'
'    MessageBox.Show("CandidateActivated: " & code & " " & name,
'                    "Top Candidate Board",
'                    MessageBoxButtons.OK,
'                    MessageBoxIcon.Information)
'End Sub
'
' =============================================================================
' MainForm에 추가할 코드 끝
' =============================================================================
