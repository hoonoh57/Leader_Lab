# Server Editing Workflow v1

Date: 2026-05-13

This repository uses a server-first editing workflow.

## Rule

Files are created or modified on GitHub first.

Local work is limited to:

```text
git pull origin main
run the versioned script
git status
```

If verification fails, update the server-side file or script, then pull again.

Do not switch to local manual editing as the normal fix path.

## Next linked rule

See:

```text
docs/powershell_script_rule_v1.md
```
