Option Strict On
Option Explicit On
Option Infer Off

Imports System
Imports System.Collections.Generic
Imports System.IO
Imports System.Windows.Forms
Imports MySql.Data.MySqlClient

Module Program
    <STAThread()>
    Public Sub Main()
        Application.EnableVisualStyles()
        Application.SetCompatibleTextRenderingDefault(False)

        LoadDotEnvFromRepoRoot()

        Dim connectionString As String = BuildConnectionString()
        Dim form As New frmTopCandidateBoard(connectionString)
        AddHandler form.CandidateActivated, AddressOf OnCandidateActivated

        Application.Run(form)
    End Sub

    Private Function BuildConnectionString() As String
        Dim raw As String = GetEnvValue("MYSQL_CONN")

        If String.IsNullOrWhiteSpace(raw) Then
            Dim host As String = GetEnvValueOrDefault("DB_HOST", "127.0.0.1")
            Dim portText As String = GetEnvValueOrDefault("DB_PORT", "3306")
            Dim userName As String = GetEnvValueOrDefault("DB_USER", "root")
            Dim password As String = GetEnvValueOrDefault("DB_PASS", String.Empty)
            Dim dbName As String = GetDatabaseName()

            Dim b As New MySqlConnectionStringBuilder()
            b.Server = host
            b.Port = Convert.ToUInt32(portText)
            b.UserID = userName
            b.Password = password
            b.Database = dbName
            b.CharacterSet = "utf8mb4"
            b.AllowUserVariables = True
            b.ConvertZeroDateTime = True
            b.SslMode = MySqlSslMode.Preferred
            Return b.ConnectionString
        End If

        Dim builder As New MySqlConnectionStringBuilder(raw)
        If String.IsNullOrWhiteSpace(builder.Database) Then
            builder.Database = GetDatabaseName()
        End If
        If String.IsNullOrWhiteSpace(builder.CharacterSet) Then
            builder.CharacterSet = "utf8mb4"
        End If
        builder.AllowUserVariables = True
        builder.ConvertZeroDateTime = True
        Return builder.ConnectionString
    End Function

    Private Function GetDatabaseName() As String
        Dim dbName As String = GetEnvValue("DB_NAME")
        If String.IsNullOrWhiteSpace(dbName) Then
            dbName = GetEnvValue("MYSQL_DATABASE")
        End If
        If String.IsNullOrWhiteSpace(dbName) Then
            dbName = GetEnvValue("MYSQL_DB")
        End If
        If String.IsNullOrWhiteSpace(dbName) Then
            dbName = "leader_lab"
        End If
        Return dbName.Trim()
    End Function

    Private Function GetEnvValue(ByVal key As String) As String
        Dim value As String = Environment.GetEnvironmentVariable(key)
        If value Is Nothing Then
            Return String.Empty
        End If
        Return value.Trim()
    End Function

    Private Function GetEnvValueOrDefault(ByVal key As String, ByVal defaultValue As String) As String
        Dim value As String = GetEnvValue(key)
        If String.IsNullOrWhiteSpace(value) Then
            Return defaultValue
        End If
        Return value
    End Function

    Private Sub LoadDotEnvFromRepoRoot()
        Dim dir As DirectoryInfo = New DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory)
        Dim i As Integer
        For i = 0 To 8
            Dim envPath As String = Path.Combine(dir.FullName, ".env")
            If File.Exists(envPath) Then
                LoadDotEnv(envPath)
                Return
            End If
            If dir.Parent Is Nothing Then
                Return
            End If
            dir = dir.Parent
        Next
    End Sub

    Private Sub LoadDotEnv(ByVal envPath As String)
        Dim lines As String() = File.ReadAllLines(envPath)
        Dim i As Integer
        For i = 0 To lines.Length - 1
            Dim line As String = lines(i).Trim()
            If line.Length = 0 OrElse line.StartsWith("#", StringComparison.Ordinal) Then
                Continue For
            End If

            Dim eq As Integer = line.IndexOf("="c)
            If eq <= 0 Then
                Continue For
            End If

            Dim key As String = line.Substring(0, eq).Trim()
            Dim value As String = line.Substring(eq + 1).Trim()
            If value.Length >= 2 Then
                If (value.StartsWith("""", StringComparison.Ordinal) AndAlso value.EndsWith("""", StringComparison.Ordinal)) OrElse
                   (value.StartsWith("'", StringComparison.Ordinal) AndAlso value.EndsWith("'", StringComparison.Ordinal)) Then
                    value = value.Substring(1, value.Length - 2)
                End If
            End If

            If Environment.GetEnvironmentVariable(key) Is Nothing Then
                Environment.SetEnvironmentVariable(key, value)
            End If
        Next
    End Sub

    Private Sub OnCandidateActivated(ByVal code As String, ByVal name As String)
        MessageBox.Show("CandidateActivated: " & code & " " & name, "Top Candidate Board Smoke Host", MessageBoxButtons.OK, MessageBoxIcon.Information)
    End Sub
End Module
