# Delivery cadence feature map

## Feature: Daily and weekly rollups

Paperboy's production subscription form is plain HTML and JavaScript. The KOMPETE React atoms and molecules are not present in this repository, so this change reuses Paperboy's existing form and status patterns instead of introducing a component system.

### UI elements → existing Paperboy patterns

| Element | Existing pattern | Use |
|---|---|---|
| Cadence control | Native `select` inside `.field` | Daily or weekly rollup |
| Weekly day control | Native `select` inside `.field` | Monday through Sunday; visible only for weekly cadence |
| Guidance | `.field-help` | Explain the 8:00 AM local schedule |
| Validation | `#intake-error.form-error` | Reuse the current accessible error region |
| Managed status | `#subscription-delivery` and `#management-summary` | Show the saved cadence and next delivery |
| Primary action | Existing `.button.button-wide` | Keep the current subscription action; no new button |

### Styling scope

- Reuse existing input/select, `.field`, `.field-help`, and responsive form rules.
- Add no custom button, card, loader, table, modal, or empty-state component.

### Data contract

- `cadence`: `daily` or `weekly`; defaults to `daily` for existing clients and rows.
- `weekly_day`: integer `0` through `6` using Python weekday numbering; defaults to Monday (`0`).
- Delivery remains 8:00 AM in the subscriber's IANA timezone.
