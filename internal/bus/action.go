package bus

// ActionCommand and ActionAck make the branch intervention a verified protocol
// step. Publishing a command is not evidence that a gateway received or
// applied it; the orchestrator advances beyond the anchor only after the
// targeted gateway acknowledges the exact run and action identifier.
type ActionCommand struct {
	RunID    string `json:"run_id"`
	ActionID string `json:"action_id"`
	Target   string `json:"target"`
	Action   string `json:"action"`
	Edge     string `json:"edge,omitempty"`
	Limit    int64  `json:"limit,omitempty"`
}

type ActionAck struct {
	RunID    string `json:"run_id"`
	ActionID string `json:"action_id"`
	Target   string `json:"target"`
	Action   string `json:"action"`
	Applied  bool   `json:"applied"`
	Detail   string `json:"detail,omitempty"`
}
