# ADR 0001: Replace Questionary with simple-term-menu for Wizard UI

## Status
Accepted

## Context
The interactive wizard previously used Questionary (prompt_toolkit-based).
In some terminal configurations, the wizard screens after the first did not
visibly update when toggling selections or moving the cursor. Inputs still
applied, but visual feedback was missing, making the wizard effectively
unusable in those environments.

We want a reliable, minimal-dependency terminal UI that works consistently
across common terminal setups.

## Decision
Replace Questionary prompts in the wizard with `simple-term-menu` for single
and multi-select menus, and use `click.confirm` / `click.prompt` for yes/no
and free-text inputs.

## Consequences
- Pros:
  - More reliable rendering across terminals.
  - Smaller surface area (no prompt_toolkit dependency for the wizard).
  - Consistent UX across all wizard screens.
- Cons:
  - Less feature-rich than prompt_toolkit (fewer styling options).
  - Slightly different interaction hints (menu-based instead of checkbox UI).

## Notes
Questionary remains suitable for simple confirmations, but the wizard no longer
depends on it. If menu behavior needs to be customized further, implement
wrappers around `simple-term-menu` in `wizard.py`.
