#!/data/data/com.termux/files/usr/bin/bash
# Read-only Level 2 / Level 3 prerequisite diagnostic. No secrets printed.
set -u
printf '%s\n' '=== Alpha Labs MCP preflight (read-only) ==='
printf 'Termux HOME: %s\n' "$HOME"
printf 'UID: %s\n' "$(id -u)"
printf '%s\n' '=== Candidate Level 2 paths ==='
for root in "$HOME/termux-level2-agent" /root/termux-level2-agent; do
  if [ -d "$root" ]; then
    printf 'Directory exists: %s\n' "$root"
    for name in policy.json level2_mcp.py; do
      if [ -f "$root/$name" ]; then printf 'Present: %s\n' "$root/$name"; else printf 'Missing: %s\n' "$root/$name"; fi
    done
  else
    printf 'Directory missing in this namespace: %s\n' "$root"
  fi
done
printf '%s\n' '=== Relevant process names (arguments and secrets suppressed) ==='
for name in proot level2_mcp.py tunnel-client; do
  if command -v pgrep >/dev/null 2>&1; then
    pgrep -f "$name" 2>/dev/null | while IFS= read -r pid; do printf '%s PID %s\n' "$name" "$pid"; done
  else
    printf 'pgrep unavailable for %s\n' "$name"
  fi
done
printf '%s\n' '=== Local readiness ==='
if command -v curl >/dev/null 2>&1; then
  curl --silent --show-error --max-time 4 --output /dev/null --write-out 'GET /readyz HTTP %{http_code}\n' http://127.0.0.1:8080/readyz || printf '%s\n' 'Local readiness request failed'
else
  printf '%s\n' 'curl unavailable'
fi
printf '%s\n' '=== Security boundary ==='
printf '%s\n' 'No process was stopped; no files were modified; no Level 3 activation was attempted.'
