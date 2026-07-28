# Simulation WebSocket Events

Endpoint:

```text
WS /v1/sessions/{session_id}/events
```

Authentication uses the same bearer token as REST. Events are JSON objects:

```json
{
  "type": "state.snapshot",
  "data": {}
}
```

MVP event types:

- `session.ready`
- `state.snapshot`
- `state.patch`
- `command.accepted`
- `command.rejected`
- `alarm.raised`
- `alarm.cleared`
- `integration.error`
- `session.completed`
- `session.failed`

`state.snapshot` data contains a full `SimulationState` from `openapi.yaml`.
`command.accepted` and `command.rejected` data contain `command_id` and optional
`code`/`message`. External payload is normalized by the application backend
before frontend delivery.
