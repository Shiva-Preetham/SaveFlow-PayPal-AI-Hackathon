param([string]$Dir, [string]$Voice = "Microsoft Zira Desktop", [int]$Rate = 0)
Add-Type -AssemblyName System.Speech
$scenes = Get-Content -Raw -Encoding UTF8 (Join-Path $Dir "scenes.json") | ConvertFrom-Json
foreach ($s in $scenes) {
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $synth.SelectVoice($Voice)
    $synth.Rate = $Rate
    $out = Join-Path $Dir ("audio_" + $s.id + ".wav")
    $synth.SetOutputToWaveFile($out)
    $synth.Speak($s.speech)
    $synth.Dispose()
    Write-Output "wrote $out"
}
