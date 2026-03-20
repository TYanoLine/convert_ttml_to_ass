Get-ChildItem $args[0] -Recurse -Filter *.ja-Jp.*.ttml | ForEach-Object {
    $filePath = $_.FullName
    # $filePath の .ja-jp～.ttmlを.assに置換
    $newFilePath = $filePath -replace '\.ja-Jp\..*\.ttml$', '.ass'
    # $newFilePath が存在するかどうかをチェック
    if (Test-Path $newFilePath) {
        Write-Output "File $newFilePath already exists. Skipping $filePath"
    } else {
        Write-Output "Converting $filePath to $newFilePath"
        python "$PSScriptRoot\convert_ttml_to_ass.py" $filePath $newFilePath
    }
}
