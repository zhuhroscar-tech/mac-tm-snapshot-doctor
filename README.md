# mac-tm-snapshot-doctor

A tiny macOS CLI for diagnosing Time Machine local snapshots that can help with eject/space issues.

## Why this tool exists

Community threads repeatedly show users blocked by Time Machine snapshots and backup state:

- "Cannot delete snapshots" on Apple Support communities
- Stuck or failing local snapshots consuming hidden system space

This tool does not delete data by default. It only reports state and prints safe, explicit commands for manual follow-up.

## Features

- List Time Machine local snapshots for a volume (`tmutil listlocalsnapshots`).
- Read `tmutil status` to detect active backup phases.
- Detect common snapshot mount paths and mounted backup-related volumes.
- Produce JSON for scripting and automation.
- Suggest conservative remediation steps.

## Install

```bash
python3 -m pip install mac-tm-snapshot-doctor
```

## Usage

```bash
# Summary report
mac-tm-snapshot-doctor

# List snapshots as JSON
mac-tm-snapshot-doctor list --volume / --json

# Report for a specific path
mac-tm-snapshot-doctor health --volume / --json
```

## Contributing

Open issues/patches at the project GitHub page.
