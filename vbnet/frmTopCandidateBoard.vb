Option Strict On
Option Explicit On
Option Infer Off

Imports System
Imports System.Data
Imports System.Drawing
Imports System.Windows.Forms
Imports MySql.Data.MySqlClient

Public Class frmTopCandidateBoard
    Inherits Form

    Public Event CandidateActivated(ByVal code As String, ByVal name As String)

    Private ReadOnly _connectionString As String
    Private ReadOnly cboMode As ComboBox
    Private ReadOnly btnRefresh As Button
    Private ReadOnly lblStatus As Label
    Private ReadOnly dgvBoard As DataGridView

    Public Sub New()
        Me.New(Environment.GetEnvironmentVariable("MYSQL_CONN"))
    End Sub

    Public Sub New(ByVal connectionString As String)
        MyBase.New()

        If String.IsNullOrWhiteSpace(connectionString) Then
            _connectionString = String.Empty
        Else
            _connectionString = connectionString.Trim()
        End If

        Me.Text = "Top Candidate Board v3.1"
        Me.StartPosition = FormStartPosition.CenterScreen
        Me.Width = 1500
        Me.Height = 850
        Me.MinimumSize = New Size(1100, 650)

        cboMode = New ComboBox()
        btnRefresh = New Button()
        lblStatus = New Label()
        dgvBoard = New DataGridView()

        InitializeLayout()
        InitializeGrid()
        InitializeModes()
    End Sub

    Private Sub InitializeLayout()
        Dim topPanel As New Panel()
        topPanel.Dock = DockStyle.Top
        topPanel.Height = 48
        topPanel.Padding = New Padding(8, 8, 8, 8)

        Dim lblMode As New Label()
        lblMode.Text = "Mode"
        lblMode.AutoSize = False
        lblMode.TextAlign = ContentAlignment.MiddleLeft
        lblMode.Width = 50
        lblMode.Dock = DockStyle.Left

        cboMode.DropDownStyle = ComboBoxStyle.DropDownList
        cboMode.Width = 180
        cboMode.Dock = DockStyle.Left

        btnRefresh.Text = "Refresh"
        btnRefresh.Width = 90
        btnRefresh.Dock = DockStyle.Left
        AddHandler btnRefresh.Click, AddressOf OnRefreshClick

        lblStatus.Text = "Ready"
        lblStatus.AutoSize = False
        lblStatus.TextAlign = ContentAlignment.MiddleLeft
        lblStatus.Dock = DockStyle.Fill
        lblStatus.Padding = New Padding(12, 0, 0, 0)

        topPanel.Controls.Add(lblStatus)
        topPanel.Controls.Add(btnRefresh)
        topPanel.Controls.Add(cboMode)
        topPanel.Controls.Add(lblMode)

        dgvBoard.Dock = DockStyle.Fill

        Me.Controls.Add(dgvBoard)
        Me.Controls.Add(topPanel)
    End Sub

    Private Sub InitializeGrid()
        dgvBoard.AllowUserToAddRows = False
        dgvBoard.AllowUserToDeleteRows = False
        dgvBoard.AllowUserToResizeRows = False
        dgvBoard.AutoGenerateColumns = False
        dgvBoard.SelectionMode = DataGridViewSelectionMode.FullRowSelect
        dgvBoard.MultiSelect = False
        dgvBoard.ReadOnly = True
        dgvBoard.RowHeadersVisible = False
        dgvBoard.BackgroundColor = Color.White
        dgvBoard.BorderStyle = BorderStyle.FixedSingle
        dgvBoard.EnableHeadersVisualStyles = False
        dgvBoard.ColumnHeadersDefaultCellStyle.BackColor = Color.FromArgb(245, 245, 245)
        dgvBoard.ColumnHeadersDefaultCellStyle.ForeColor = Color.Black
        dgvBoard.ColumnHeadersDefaultCellStyle.Font = New Font(dgvBoard.Font, FontStyle.Bold)
        dgvBoard.RowTemplate.Height = 24

        AddTextColumn("colRank", "순위", "ui_rank", 55, DataGridViewContentAlignment.MiddleRight)
        AddTextColumn("colActionKr", "한글액션", "board_action_kr_v2_8", 105, DataGridViewContentAlignment.MiddleCenter)
        AddTextColumn("colAction", "액션", "board_action_v2_8", 135, DataGridViewContentAlignment.MiddleCenter)
        AddTextColumn("colCode", "종목코드", "code", 80, DataGridViewContentAlignment.MiddleCenter)
        AddTextColumn("colName", "종목명", "name", 120, DataGridViewContentAlignment.MiddleLeft)
        AddTextColumn("colTickerLabel", "라벨", "ticker_label", 150, DataGridViewContentAlignment.MiddleLeft)
        AddTextColumn("colEntryTime", "진입시간", "entry_time_text", 80, DataGridViewContentAlignment.MiddleCenter)
        AddTextColumn("colEntryPrice", "진입가", "entry_price", 80, DataGridViewContentAlignment.MiddleRight, "N0")
        AddTextColumn("colExpected", "기대%", "expected_return_pct", 75, DataGridViewContentAlignment.MiddleRight, "N2")
        AddTextColumn("colMae", "MAE%", "mae_risk_pct", 75, DataGridViewContentAlignment.MiddleRight, "N2")
        AddTextColumn("colAmount", "누적억", "start_cum_amount_eok", 75, DataGridViewContentAlignment.MiddleRight, "N1")
        AddTextColumn("colTickScore", "틱확정", "tick_confirm_score_v2_6", 75, DataGridViewContentAlignment.MiddleRight, "N1")
        AddTextColumn("colTickIntensity", "틱강도", "tick_intensity_v2_6", 75, DataGridViewContentAlignment.MiddleRight, "N2")
        AddTextColumn("colBuyRatio", "매수틱%", "buy_tick_ratio_v2_6", 80, DataGridViewContentAlignment.MiddleRight, "N1")
        AddTextColumn("colLargeTrade", "대량억", "large_trade_amount_eok_v2_6", 75, DataGridViewContentAlignment.MiddleRight, "N1")
        AddTextColumn("colBidPressure", "매수압", "hoga_bid_pressure_v2_6", 75, DataGridViewContentAlignment.MiddleRight, "N1")
        AddTextColumn("colAskAbsorb", "매도흡수", "hoga_ask_absorption_v2_6", 80, DataGridViewContentAlignment.MiddleRight, "N1")
        AddTextColumn("colSpread", "스프레드", "spread_risk_v2_6", 80, DataGridViewContentAlignment.MiddleRight, "N2")
        AddTextColumn("colNext", "다음행동", "final_next_action_v2_8", 130, DataGridViewContentAlignment.MiddleLeft)
        AddTextColumn("colReason", "사유", "board_reason_v2_8", 360, DataGridViewContentAlignment.MiddleLeft)
        AddTextColumn("colSnapshot", "스냅샷", "realtime_snapshot_time", 150, DataGridViewContentAlignment.MiddleCenter)
        AddTextColumn("colSource", "소스", "realtime_source_tag", 110, DataGridViewContentAlignment.MiddleLeft)

        AddHandler dgvBoard.CellDoubleClick, AddressOf OnGridCellDoubleClick
        AddHandler dgvBoard.RowPrePaint, AddressOf OnGridRowPrePaint
        AddHandler dgvBoard.DataBindingComplete, AddressOf OnGridDataBindingComplete
    End Sub

    Private Sub InitializeModes()
        cboMode.Items.Clear()
        cboMode.Items.Add("LIVE_COMPACT")
        cboMode.Items.Add("TEST_ALL")
        cboMode.Items.Add("AUTO_BUY_ONLY")
        cboMode.Items.Add("WATCH_ONLY")
        cboMode.Items.Add("REJECT_ONLY")
        cboMode.SelectedIndex = 0
    End Sub

    Private Sub AddTextColumn(ByVal columnName As String,
                              ByVal headerText As String,
                              ByVal dataPropertyName As String,
                              ByVal width As Integer,
                              ByVal align As DataGridViewContentAlignment,
                              Optional ByVal formatText As String = "")
        Dim col As New DataGridViewTextBoxColumn()
        col.Name = columnName
        col.HeaderText = headerText
        col.DataPropertyName = dataPropertyName
        col.Width = width
        col.DefaultCellStyle.Alignment = align
        If Not String.IsNullOrWhiteSpace(formatText) Then
            col.DefaultCellStyle.Format = formatText
        End If
        dgvBoard.Columns.Add(col)
    End Sub

    Private Sub OnRefreshClick(ByVal sender As Object, ByVal e As EventArgs)
        RefreshBoard()
    End Sub

    Public Sub RefreshBoard()
        If String.IsNullOrWhiteSpace(_connectionString) Then
            lblStatus.Text = "MYSQL_CONN 또는 생성자 connectionString이 비어 있습니다."
            Return
        End If

        Dim mode As String = GetSelectedMode()
        Dim sqlText As String = BuildTopCandidateBoardSql(mode)
        Dim table As New DataTable("TopCandidateBoard")

        Try
            Using conn As New MySqlConnection(_connectionString)
                conn.Open()
                Using cmd As New MySqlCommand(sqlText, conn)
                    cmd.CommandTimeout = 30
                    Using adapter As New MySqlDataAdapter(cmd)
                        adapter.Fill(table)
                    End Using
                End Using
            End Using

            EnsureUiRankColumn(table, mode)
            dgvBoard.DataSource = table
            lblStatus.Text = mode & " / rows=" & table.Rows.Count.ToString("N0") & " / " & DateTime.Now.ToString("HH:mm:ss")
        Catch ex As Exception
            lblStatus.Text = "Refresh failed: " & ex.Message
        End Try
    End Sub

    Private Function GetSelectedMode() As String
        If cboMode.SelectedItem Is Nothing Then
            Return "LIVE_COMPACT"
        End If
        Dim selected As String = Convert.ToString(cboMode.SelectedItem)
        If String.IsNullOrWhiteSpace(selected) Then
            Return "LIVE_COMPACT"
        End If
        Return selected.Trim()
    End Function

    Private Function BuildTopCandidateBoardSql(ByVal mode As String) As String
        Dim selectColumns As String = BuildSelectColumnSql()

        Select Case mode
            Case "LIVE_COMPACT"
                Return selectColumns & " FROM supertrend_top_candidate_board_dedup_view_v2_9 WHERE ui_live_compact_flag_v2_9 = 1 ORDER BY dedup_final_rank_no_v2_9 ASC"
            Case "TEST_ALL"
                Return selectColumns & " FROM supertrend_top_candidate_board_raw_view_v2_9 WHERE ui_test_all_flag_v2_9 = 1 ORDER BY final_rank_no_v2_8 ASC"
            Case "AUTO_BUY_ONLY"
                Return selectColumns & " FROM supertrend_top_candidate_board_dedup_view_v2_9 WHERE ui_auto_buy_only_flag_v2_9 = 1 ORDER BY dedup_final_rank_no_v2_9 ASC"
            Case "WATCH_ONLY"
                Return selectColumns & " FROM supertrend_top_candidate_board_dedup_view_v2_9 WHERE ui_watch_only_flag_v2_9 = 1 ORDER BY dedup_final_rank_no_v2_9 ASC"
            Case "REJECT_ONLY"
                Return selectColumns & " FROM supertrend_top_candidate_board_raw_view_v2_9 WHERE ui_reject_only_flag_v2_9 = 1 ORDER BY final_rank_no_v2_8 ASC"
            Case Else
                Return selectColumns & " FROM supertrend_top_candidate_board_dedup_view_v2_9 WHERE ui_live_compact_flag_v2_9 = 1 ORDER BY dedup_final_rank_no_v2_9 ASC"
        End Select
    End Function

    Private Function BuildSelectColumnSql() As String
        Return "SELECT " &
               "dedup_final_rank_no_v2_9, " &
               "dedup_action_rank_no_v2_9, " &
               "final_rank_no_v2_8, " &
               "action_rank_no_v2_8, " &
               "board_action_v2_8, " &
               "board_action_kr_v2_8, " &
               "code, " &
               "name, " &
               "ticker_label, " &
               "entry_time_text, " &
               "entry_price, " &
               "expected_return_pct, " &
               "mae_risk_pct, " &
               "start_cum_amount_eok, " &
               "tick_confirm_score_v2_6, " &
               "tick_intensity_v2_6, " &
               "buy_tick_ratio_v2_6, " &
               "large_trade_amount_eok_v2_6, " &
               "hoga_bid_pressure_v2_6, " &
               "hoga_ask_absorption_v2_6, " &
               "spread_risk_v2_6, " &
               "final_next_action_v2_8, " &
               "board_reason_v2_8, " &
               "realtime_snapshot_time, " &
               "realtime_source_tag"
    End Function

    Private Sub EnsureUiRankColumn(ByVal table As DataTable, ByVal mode As String)
        If Not table.Columns.Contains("ui_rank") Then
            table.Columns.Add("ui_rank", GetType(Integer))
        End If

        Dim useDedupRank As Boolean = Not String.Equals(mode, "TEST_ALL", StringComparison.OrdinalIgnoreCase) AndAlso
                                      Not String.Equals(mode, "REJECT_ONLY", StringComparison.OrdinalIgnoreCase)

        Dim i As Integer
        For i = 0 To table.Rows.Count - 1
            Dim row As DataRow = table.Rows(i)
            If useDedupRank AndAlso table.Columns.Contains("dedup_final_rank_no_v2_9") AndAlso Not IsDBNull(row("dedup_final_rank_no_v2_9")) Then
                row("ui_rank") = Convert.ToInt32(row("dedup_final_rank_no_v2_9"))
            ElseIf table.Columns.Contains("final_rank_no_v2_8") AndAlso Not IsDBNull(row("final_rank_no_v2_8")) Then
                row("ui_rank") = Convert.ToInt32(row("final_rank_no_v2_8"))
            Else
                row("ui_rank") = i + 1
            End If
        Next
    End Sub

    Private Sub OnGridDataBindingComplete(ByVal sender As Object, ByVal e As DataGridViewBindingCompleteEventArgs)
        dgvBoard.ClearSelection()
    End Sub

    Private Sub OnGridRowPrePaint(ByVal sender As Object, ByVal e As DataGridViewRowPrePaintEventArgs)
        If e.RowIndex < 0 OrElse e.RowIndex >= dgvBoard.Rows.Count Then
            Return
        End If

        Dim row As DataGridViewRow = dgvBoard.Rows(e.RowIndex)
        Dim actionValue As String = GetCellString(row, "colAction")

        If String.Equals(actionValue, "AUTO_BUY_READY", StringComparison.OrdinalIgnoreCase) Then
            row.DefaultCellStyle.BackColor = Color.FromArgb(230, 255, 235)
            row.DefaultCellStyle.ForeColor = Color.FromArgb(0, 80, 30)
        ElseIf String.Equals(actionValue, "WATCH_HOGA_TICK", StringComparison.OrdinalIgnoreCase) Then
            row.DefaultCellStyle.BackColor = Color.FromArgb(255, 250, 225)
            row.DefaultCellStyle.ForeColor = Color.FromArgb(90, 70, 0)
        ElseIf String.Equals(actionValue, "REJECT", StringComparison.OrdinalIgnoreCase) Then
            row.DefaultCellStyle.BackColor = Color.FromArgb(245, 245, 245)
            row.DefaultCellStyle.ForeColor = Color.FromArgb(110, 110, 110)
        Else
            row.DefaultCellStyle.BackColor = Color.White
            row.DefaultCellStyle.ForeColor = Color.Black
        End If
    End Sub

    Private Function GetCellString(ByVal row As DataGridViewRow, ByVal columnName As String) As String
        If Not dgvBoard.Columns.Contains(columnName) Then
            Return String.Empty
        End If
        Dim value As Object = row.Cells(columnName).Value
        If value Is Nothing OrElse Convert.IsDBNull(value) Then
            Return String.Empty
        End If
        Return Convert.ToString(value)
    End Function

    Private Sub OnGridCellDoubleClick(ByVal sender As Object, ByVal e As DataGridViewCellEventArgs)
        If e.RowIndex < 0 OrElse e.RowIndex >= dgvBoard.Rows.Count Then
            Return
        End If

        Dim row As DataGridViewRow = dgvBoard.Rows(e.RowIndex)
        Dim code As String = GetCellString(row, "colCode").Trim()
        Dim name As String = GetCellString(row, "colName").Trim()

        If code.Length = 0 Then
            Return
        End If

        RaiseEvent CandidateActivated(code, name)
    End Sub
End Class
