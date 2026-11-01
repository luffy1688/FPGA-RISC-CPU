# Windows PowerShell 5.1 / PowerShell 7. No modules or hardware drivers installed.
[CmdletBinding()]
param(
    [ValidateRange(1,1000)][int]$PollIntervalMilliseconds = 50,
    [string]$Port = 'COM10',
    [ValidateSet(115200)][int]$Baud = 115200,
    [ValidateRange(1,604800)][int]$DurationSeconds = 3600,
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '../../07_runs/board'),
    [string]$CommandFile = '',
    [string]$StopFile = '',
    [ValidateRange(0,1000)][int]$CharacterIntervalMilliseconds = 0,
    [ValidateRange(0,1000)][int]$ProbeCharacterIntervalMilliseconds = 2
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
if (-not $StopFile) { $StopFile = Join-Path $OutputDirectory 'capture.stop' }

$taskStart = [DateTimeOffset]::Now
$taskId = 'uart_' + $taskStart.ToString('yyyyMMdd_HHmmss_fff')
$taskEventsPath = Join-Path $OutputDirectory ($taskId + '.jsonl')
$taskTextPath = Join-Path $OutputDirectory ($taskId + '.txt')
$taskRawPath = Join-Path $OutputDirectory ($taskId + '.bin')
$taskStatusPath = Join-Path $OutputDirectory 'capture_status.json'
$taskStatusTempPath = Join-Path $OutputDirectory ($taskId + '.status.tmp')
$taskUtf8 = [Text.UTF8Encoding]::new($false)
$taskEvents = [IO.StreamWriter]::new($taskEventsPath, $false, $taskUtf8)
$taskTextWriter = [IO.StreamWriter]::new($taskTextPath, $false, $taskUtf8)
$taskRaw = [IO.FileStream]::new($taskRawPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
$taskSerial = [IO.Ports.SerialPort]::new($Port, $Baud, [IO.Ports.Parity]::None, 8, [IO.Ports.StopBits]::One)
$taskSerial.Handshake = [IO.Ports.Handshake]::None
$taskSerial.DtrEnable = $false
$taskSerial.RtsEnable = $false
$taskSerial.ReadTimeout = 500
$taskSerial.WriteTimeout = 2000
$taskDecoder = $taskUtf8.GetDecoder()
$taskReady = $false
$taskProbeSent = $false
$taskRxCount = 0L
$taskTxCount = 0L
$taskLineBuffer = ''
$taskLastLine = ''
$taskLastCommandError = ''
$taskStatusWarningActive = $false
$taskSeenCommands = [Collections.Generic.HashSet[string]]::new()
$taskFinalState = 'completed'
$taskFailure = $null

function Write-CaptureEvent([string]$Direction, [object]$Data) {
    $taskEvents.WriteLine((@{
        at = [DateTimeOffset]::Now.ToString('o')
        direction = $Direction
        data = $Data
    } | ConvertTo-Json -Compress -Depth 6))
    $taskEvents.Flush()
}

function Write-CaptureStatus([string]$State) {
    $taskStatusJson = @{
        capture_id = $taskId; state = $State; source = 'physical_serial'
        port = $Port; baud = $Baud; data_bits = 8; parity = 'none'; stop_bits = 1
        flow_control = 'none'; dtr = $false; rts = $false
        ready = $taskReady; probe_sent = $taskProbeSent; serial_open = $taskSerial.IsOpen
        rx_bytes = $taskRxCount; tx_bytes = $taskTxCount; last_line = $taskLastLine
        pending_text = $taskLineBuffer; text_path = $taskTextPath
        events_path = $taskEventsPath; raw_path = $taskRawPath; stop_file = $StopFile
        started_at = $taskStart.ToString('o'); updated_at = [DateTimeOffset]::Now.ToString('o')
        done_bit_checked = $false; error = $taskFailure
    } | ConvertTo-Json -Depth 4
    # Replace on the same filesystem; readers see an old or new complete file.
    # A reader that does not share deletion can briefly lock the destination.
    for ($taskStatusAttempt = 0; $taskStatusAttempt -lt 3; $taskStatusAttempt++) {
        try {
            [IO.File]::WriteAllText($taskStatusTempPath, $taskStatusJson, $taskUtf8)
            if ([IO.File]::Exists($taskStatusPath)) {
                # PowerShell coerces $null to an empty string for string
                # arguments; NullString supplies a real null backup filename.
                [IO.File]::Replace($taskStatusTempPath, $taskStatusPath, [System.Management.Automation.Language.NullString]::Value)
            } else {
                [IO.File]::Move($taskStatusTempPath, $taskStatusPath)
            }
            $script:taskStatusWarningActive = $false
            return
        } catch [IO.IOException] {
            if ($taskStatusAttempt -lt 2) { Start-Sleep -Milliseconds 20; continue }
            if (-not $taskStatusWarningActive) {
                Write-CaptureEvent 'WARN' @{reason = 'status_replace_busy';message = $_.Exception.Message}
                $script:taskStatusWarningActive = $true
            }
        }
    }
}

function Add-CaptureText([string]$Chunk) {
    if (-not $Chunk) { return }
    $taskTextWriter.Write($Chunk)
    $taskTextWriter.Flush()
    $script:taskLineBuffer += $Chunk
    while ($taskLineBuffer.Contains("`n")) {
        $taskLineEnd = $taskLineBuffer.IndexOf("`n")
        $script:taskLastLine = $taskLineBuffer.Substring(0, $taskLineEnd).TrimEnd("`r")
        $script:taskLineBuffer = $taskLineBuffer.Substring($taskLineEnd + 1)
        Write-Output ('RX ' + $taskLastLine)
        if ($taskLastLine -eq 'NR_READY') { $script:taskReady = $true }
        # Reset/boot output invalidates a READY observed before this restart.
        if ($taskLastLine.StartsWith('NeedleRV-X ') -or $taskLastLine.StartsWith('NR_BUILD ')) {
            $script:taskReady = $false
        }
    }
}

function Read-AvailableSerial {
    while ($taskSerial.BytesToRead -gt 0) {
        $taskAvailable = [Math]::Min($taskSerial.BytesToRead, 4096)
        $taskBuffer = [byte[]]::new($taskAvailable)
        $taskRead = $taskSerial.Read($taskBuffer, 0, $taskBuffer.Length)
        if ($taskRead -le 0) { break }
        $taskRaw.Write($taskBuffer, 0, $taskRead)
        $taskRaw.Flush()
        $script:taskRxCount += $taskRead
        $taskChars = [char[]]::new($taskUtf8.GetMaxCharCount($taskRead))
        $taskCharCount = $taskDecoder.GetChars($taskBuffer, 0, $taskRead, $taskChars, 0, $false)
        $taskChunk = [string]::new($taskChars, 0, $taskCharCount)
        Write-CaptureEvent 'RX' @{
            bytes_base64 = [Convert]::ToBase64String($taskBuffer, 0, $taskRead)
            text = $taskChunk
        }
        Add-CaptureText $taskChunk
    }
}

function Read-CaptureCommand {
    if (-not $CommandFile -or -not (Test-Path -LiteralPath $CommandFile -PathType Leaf)) { return $null }
    $taskCommandContents = ''
    try {
        $taskCommandContents = Get-Content -LiteralPath $CommandFile -Raw -Encoding UTF8
        $taskCommand = $taskCommandContents | ConvertFrom-Json
        if ($null -eq $taskCommand -or $taskCommand -is [Array]) { throw 'CommandFile must contain one JSON object.' }
        $taskIdProperty = $taskCommand.PSObject.Properties['id']
        $taskTextProperty = $taskCommand.PSObject.Properties['text']
        if (-not $taskIdProperty -or $taskIdProperty.Value -isnot [string] -or
            [string]::IsNullOrWhiteSpace($taskIdProperty.Value)) { throw 'Command id must be a nonempty string.' }
        if (-not $taskTextProperty -or $taskTextProperty.Value -isnot [string] -or
            [string]::IsNullOrEmpty($taskTextProperty.Value)) { throw 'Command text must be a nonempty string.' }
        $taskCommandId = [string]$taskIdProperty.Value
        if ($taskSeenCommands.Contains($taskCommandId)) { return $null }
        $taskCommandText = [string]$taskTextProperty.Value
        if ($taskCommandText.Contains("`n") -or $taskCommandText.Contains("`r") -or
            $taskUtf8.GetByteCount($taskCommandText) -gt 64) {
            throw 'Command must be one UTF-8 line of at most 64 bytes.'
        }
        $taskIsProbe = $false
        $taskProbeProperty = $taskCommand.PSObject.Properties['probe']
        if ($taskProbeProperty) {
            if ($taskProbeProperty.Value -isnot [bool]) { throw 'probe must be a JSON boolean.' }
            $taskIsProbe = [bool]$taskProbeProperty.Value
        }
        if ($taskIsProbe -and $taskCommandText -cne ':probe') {
            throw 'probe:true permits only the exact diagnostic command :probe.'
        }
        if ($taskIsProbe -and $taskProbeSent) { throw 'Only one explicit diagnostic probe is permitted per capture.' }
        $script:taskLastCommandError = ''
        return @{id = $taskCommandId; text = $taskCommandText; probe = $taskIsProbe}
    } catch {
        # A producer can be partway through updating the command file. Keep RX
        # running and report each changed invalid payload once; never send it.
        $taskCommandError = $taskCommandContents + "`n" + $_.Exception.Message
        if ($taskCommandError -ne $taskLastCommandError) {
            Write-CaptureEvent 'COMMAND_ERROR' $_.Exception.Message
            $script:taskLastCommandError = $taskCommandError
        }
        return $null
    }
}

function Send-CaptureCommand([hashtable]$Command) {
    if (-not $taskReady -and -not $Command.probe) { return }
    $taskTx = $taskUtf8.GetBytes($Command.text + "`n")
    $taskInterval = $CharacterIntervalMilliseconds
    if ($Command.probe) { $taskInterval = $ProbeCharacterIntervalMilliseconds }
    $script:taskReady = $false
    if ($Command.probe) { $script:taskProbeSent = $true }
    [void]$taskSeenCommands.Add($Command.id)
    $taskWritten = 0
    try {
        if ($taskInterval -eq 0) {
            $taskSerial.Write($taskTx, 0, $taskTx.Length)
            $taskWritten = $taskTx.Length
            $script:taskTxCount += $taskWritten
        } else {
            for ($taskByteIndex = 0; $taskByteIndex -lt $taskTx.Length; $taskByteIndex++) {
                $taskSerial.Write($taskTx, $taskByteIndex, 1)
                $taskWritten++
                $script:taskTxCount++
                if ($taskByteIndex + 1 -lt $taskTx.Length) { Start-Sleep -Milliseconds $taskInterval }
            }
        }
    } finally {
        Write-CaptureEvent 'TX' @{
            id = $Command.id; text = $Command.text; probe = $Command.probe
            character_interval_ms = $taskInterval; bytes_written = $taskWritten
            completed = ($taskWritten -eq $taskTx.Length)
            bytes_base64 = [Convert]::ToBase64String($taskTx, 0, $taskWritten)
        }
    }
    Write-Output ('TX ' + $Command.text)
    Write-CaptureStatus 'open'
}

try {
    Write-CaptureEvent 'INFO' @{
        schema = 'needlervx.uart.capture.v1'; source = 'physical_serial'
        port = $Port; baud = $Baud; data_bits = 8; stop_bits = 1
        parity = 'none'; flow_control = 'none'; dtr = $false; rts = $false
        done_bit_checked = $false
    }
    # An existing stop file must not be silently deleted or ignored.
    if (Test-Path -LiteralPath $StopFile) {
        $taskFinalState = 'stopped'
        Write-Output 'CAPTURE_STOPPED stop file already exists; port was not opened.'
    } else {
        $taskSerial.Open()
        Write-CaptureStatus 'open'
        Write-Output "CAPTURE_OPEN $Port $Baud; RX log: $taskTextPath; stop file: $StopFile"
        $taskDeadline = [DateTime]::UtcNow.AddSeconds($DurationSeconds)
        $taskNextStatus = [DateTime]::UtcNow.AddSeconds(1)
        while ([DateTime]::UtcNow -lt $taskDeadline) {
            Read-AvailableSerial
            if (Test-Path -LiteralPath $StopFile) {
                $taskFinalState = 'stopped'
                break
            }
            $taskPendingCommand = Read-CaptureCommand
            if ($null -ne $taskPendingCommand) { Send-CaptureCommand $taskPendingCommand }
            if ([DateTime]::UtcNow -ge $taskNextStatus) {
                Write-CaptureStatus 'open'
                $taskNextStatus = [DateTime]::UtcNow.AddSeconds(1)
            }
            Start-Sleep -Milliseconds $PollIntervalMilliseconds
        }
    }
} catch {
    $taskFinalState = 'error'
    $taskFailure = $_.Exception.Message
    Write-CaptureEvent 'ERROR' $taskFailure
    Write-Output ('CAPTURE_ERROR ' + $taskFailure)
} finally {
    # Closing precedes final status: stopped/completed means Xshell can reopen.
    if ($taskSerial.IsOpen) { $taskSerial.Close() }
    $taskFinalChars = [char[]]::new($taskUtf8.GetMaxCharCount(0))
    $taskFinalCharCount = $taskDecoder.GetChars([byte[]]::new(0), 0, 0, $taskFinalChars, 0, $true)
    if ($taskFinalCharCount -gt 0) {
        $taskFinalChunk = [string]::new($taskFinalChars, 0, $taskFinalCharCount)
        Add-CaptureText $taskFinalChunk
        Write-CaptureEvent 'DECODE_FLUSH' @{text = $taskFinalChunk}
    }
    Write-CaptureEvent 'CLOSE' @{state = $taskFinalState; error = $taskFailure}
    Write-CaptureStatus $taskFinalState
    $taskSerial.Dispose()
    $taskRaw.Dispose()
    $taskTextWriter.Dispose()
    $taskEvents.Dispose()
    if (Test-Path -LiteralPath $taskStatusTempPath) {
        Remove-Item -LiteralPath $taskStatusTempPath -Force
    }
}
if ($taskFinalState -eq 'error') { exit 1 }
