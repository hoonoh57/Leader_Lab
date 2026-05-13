Option Strict On
Option Explicit On
Option Infer Off

Imports System
Imports System.Windows.Forms

Module Program
    <STAThread()>
    Public Sub Main()
        Application.EnableVisualStyles()
        Application.SetCompatibleTextRenderingDefault(False)

        Dim connectionString As String = Environment.GetEnvironmentVariable("MYSQL_CONN")
        Dim form As New frmTopCandidateBoard(connectionString)
        AddHandler form.CandidateActivated, AddressOf OnCandidateActivated

        Application.Run(form)
    End Sub

    Private Sub OnCandidateActivated(ByVal code As String, ByVal name As String)
        MessageBox.Show("CandidateActivated: " & code & " " & name, "Top Candidate Board Smoke Host", MessageBoxButtons.OK, MessageBoxIcon.Information)
    End Sub
End Module
