#!/usr/bin/env bash
set -euo pipefail

pilot_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
inklecate="${INKLECATE:-$pilot_root/.tooling/inklecate/inklecate}"
ink_runtime="${INK_RUNTIME:-$(dirname -- "$inklecate")/ink-engine-runtime.dll}"
prerequisite() {
    printf '%s\n' "INK PREREQUISITE: $1" >&2
    exit 66
}
[[ -x "$inklecate" ]] || prerequisite "Set INKLECATE to the verified standalone compiler."
[[ -f "$ink_runtime" ]] || prerequisite "Set INK_RUNTIME to the matching release DLL."
command -v shasum >/dev/null 2>&1 || prerequisite "shasum is required to verify tools."
command -v dotnet >/dev/null 2>&1 || prerequisite ".NET 8 SDK is required."
[[ "$(dotnet --version)" == 8.* ]] || prerequisite "Select a compatible .NET 8 SDK."
[[ "$(shasum -a 256 "$inklecate" | cut -d ' ' -f 1)" == df0f53f321203bb5f7ccfe7debb3f0f9abb3f328a56363bef4dde605baf17e5e ]] ||
    prerequisite "Compiler fingerprint differs from the pinned macOS release."
[[ "$(shasum -a 256 "$ink_runtime" | cut -d ' ' -f 1)" == 8ab9e923e6563ac94e5a2a9289fd8fe4f97acccf1c20cd9aa05c4e20e250d51a ]] ||
    prerequisite "Runtime fingerprint differs from the pinned release DLL."

scratch="$(mktemp -d "${TMPDIR:-/tmp}/ridge-pack.XXXXXX")"
cleanup() {
    rm -rf -- "$scratch"
    printf '%s\n' 'CLEANUP standalone Ink scratch removed'
}
trap cleanup EXIT

"$inklecate" -o "$scratch/quest.json" "$pilot_root/quest.ink" > "$scratch/compile.log" 2>&1 || {
    cat "$scratch/compile.log" >&2
    exit 1
}
if [[ -s "$scratch/compile.log" ]]; then
    cat "$scratch/compile.log" >&2
    exit 1
fi
printf '%s\n' 'PASS official Ink compilation without diagnostics'

cp "$pilot_root/runtime-check/runtime-check.csproj" "$pilot_root/runtime-check/program.cs" "$scratch/"
printf '%s\n' '<configuration><packageSources><clear /></packageSources></configuration>' > "$scratch/NuGet.Config"
export DOTNET_CLI_HOME="$scratch/dotnet-home"
export DOTNET_CLI_TELEMETRY_OPTOUT=1
export DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1
export DOTNET_NOLOGO=1
export NUGET_PACKAGES="$scratch/nuget"

dotnet build "$scratch/runtime-check.csproj" --nologo --verbosity quiet -p:InkRuntimePath="$ink_runtime"
dotnet "$scratch/bin/Debug/net8.0/runtime-check.dll" "$scratch/quest.json" "$pilot_root/route-traces.json"
