param(
    [Parameter(Mandatory = $true)]
    [string] $Pcap,
    [string] $AuthorizedDnp3Sources = ""
)

$ErrorActionPreference = "Stop"
$resolvedPcap = (Resolve-Path -LiteralPath $Pcap).Path
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$pcapDirectory = Split-Path -Parent $resolvedPcap
$pcapName = Split-Path -Leaf $resolvedPcap
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$zeekOutput = Join-Path $projectRoot "output\zeek-$timestamp"
$suricataOutput = Join-Path $projectRoot "output\suricata-$timestamp"
$outputDirectory = Join-Path $projectRoot "output"
New-Item -ItemType Directory -Force -Path $zeekOutput, $suricataOutput | Out-Null

$pcapMount = "${pcapDirectory}:/pcap:ro"
$zeekMount = "${zeekOutput}:/logs"
$suricataMount = "${suricataOutput}:/logs"
$suricataRules = Join-Path $projectRoot "config\suricata\local.rules"
$suricataRulesMount = "${suricataRules}:/rules/local.rules:ro"
$zeekImage = "ics-ids-zeek:local"

docker build -f (Join-Path $projectRoot "Dockerfile.zeek") -t $zeekImage $projectRoot
if ($LASTEXITCODE -ne 0) { throw "Zeek image build returned exit code $LASTEXITCODE" }

docker run --rm -v $pcapMount -v $zeekMount -w /logs $zeekImage zeek -e "redef LogAscii::use_json = T;" -Cr "/pcap/$pcapName" icsnpp-dnp3
if ($LASTEXITCODE -ne 0) { throw "Zeek returned exit code $LASTEXITCODE" }

docker run --rm -v $pcapMount -v $suricataMount -v $suricataRulesMount jasonish/suricata:8.0.2 -r "/pcap/$pcapName" -S /rules/local.rules --init-errors-fatal -l /logs
if ($LASTEXITCODE -ne 0) { throw "Suricata returned exit code $LASTEXITCODE" }

$outputMount = "${outputDirectory}:/data"
$ingestArgs = @("python", "-m", "ics_ids.ingest_sensor_logs", "--alerts", "/data/alerts.jsonl")
$suricataEve = "/data/$(Split-Path -Leaf $suricataOutput)/eve.json"
$zeekControl = "/data/$(Split-Path -Leaf $zeekOutput)/dnp3_control.log"
$zeekDnp3 = "/data/$(Split-Path -Leaf $zeekOutput)/dnp3.log"
if (Test-Path -LiteralPath (Join-Path $suricataOutput "eve.json")) { $ingestArgs += @("--suricata", $suricataEve) }
if (Test-Path -LiteralPath (Join-Path $zeekOutput "dnp3_control.log")) {
    $ingestArgs += @("--dnp3-control", $zeekControl)
} elseif (Test-Path -LiteralPath (Join-Path $zeekOutput "dnp3.log")) {
    $ingestArgs += @("--dnp3-control", $zeekDnp3)
}
if ($AuthorizedDnp3Sources) { $ingestArgs += @("--authorized-sources", $AuthorizedDnp3Sources) }

$composeFile = Join-Path $projectRoot "compose.yaml"
docker compose -f $composeFile build detector
if ($LASTEXITCODE -ne 0) { throw "Detector image build returned exit code $LASTEXITCODE" }
docker compose -f $composeFile run --rm --no-deps -v $outputMount detector @ingestArgs
if ($LASTEXITCODE -ne 0) { throw "Sensor alert normalization returned exit code $LASTEXITCODE" }

Write-Host "Zeek output: $zeekOutput"
Write-Host "Suricata output: $suricataOutput"
Write-Host "Unified alerts: $(Join-Path $outputDirectory 'alerts.jsonl')"
