package fingerprint_test

import (
	"fmt"
	"testing"

	"github.com/TODO-OWNER/csc-iot/internal/fingerprint"
)

func ids(from, n int) []string {
	out := make([]string, n)
	for i := range out {
		out[i] = fmt.Sprintf("e%04d", from+i)
	}
	return out
}

func base() fingerprint.Structural {
	return fingerprint.Structural{
		LogicalTick: 120, ConfigHash: "cfg", FaultPhase: "F1@0.12",
		Routing:    map[string]string{"gw00": "edge00", "gw01": "edge01"},
		RateLimits: map[string]float64{"gw00": 1.0, "gw01": 0.6},
		RateTokens: map[string]float64{"gw00": 12.5, "gw01": 3.0},
		Queues: map[string]fingerprint.Queue{
			"edge00": fingerprint.HashQueue(ids(1001, 48)),
			"edge01": fingerprint.HashQueue(ids(2001, 12)),
		},
		Retries: map[string]fingerprint.RetryState{
			"gw00": {
				PendingHash:    "abc",
				AttemptCounts:  map[string]int{"e1001": 2},
				BackoffDueTick: map[string]int64{"e1001": 126},
			},
		},
		TimeoutDueTick:      map[string]int64{"edge00": 140},
		ServicePlacement:    map[string]string{"svc0": "edge00"},
		ReplicaState:        map[string]int{"svc0": 1},
		PendingMigration:    map[string]string{},
		EdgeCapacity:        map[string]float64{"edge00": 160},
		SeqPositions:        map[string]uint64{"gw00": 9001, "gw01": 8800},
		ProcessedCounts:     map[string]int64{"edge00": 40000},
		ActionHistory:       []string{"NO_OP", "REROUTE"},
		TransportQuiescence: map[string]uint64{"end:gw00": 9001, "drained:edge00:gw00": 9001},
	}
}

// The failure that looks like success: identical depth, different contents.
func TestSameDepthDifferentContentsIsCaught(t *testing.T) {
	a, b := base(), base()
	b.Queues["edge00"] = fingerprint.HashQueue(ids(1002, 48)) // shifted by one event
	if a.Queues["edge00"].Length != b.Queues["edge00"].Length {
		t.Fatal("test setup: lengths should be equal")
	}
	if a.Hash() == b.Hash() {
		t.Fatal("two queues of equal depth holding different events hashed the same; " +
			"this would present as a valid common anchor")
	}
	d := a.Diff(b)
	if len(d) == 0 || !containsSub(d[0], "different contents") {
		t.Fatalf("Diff must say the contents differ, got %v", d)
	}
}

// Hidden future-relevant state that queue depth cannot see.
func TestLatentStateIsCovered(t *testing.T) {
	a := base()
	cases := map[string]func(*fingerprint.Structural){
		"retry pending":     func(s *fingerprint.Structural) { r := s.Retries["gw00"]; r.PendingHash = "zzz"; s.Retries["gw00"] = r },
		"retry attempts":    func(s *fingerprint.Structural) { s.Retries["gw00"].AttemptCounts["e1001"] = 3 },
		"backoff deadline":  func(s *fingerprint.Structural) { s.Retries["gw00"].BackoffDueTick["e1001"] = 130 },
		"token bucket":      func(s *fingerprint.Structural) { s.RateTokens["gw00"] = 0.5 },
		"timeout deadline":  func(s *fingerprint.Structural) { s.TimeoutDueTick["edge00"] = 141 },
		"service placement": func(s *fingerprint.Structural) { s.ServicePlacement["svc0"] = "edge01" },
		"replica state":     func(s *fingerprint.Structural) { s.ReplicaState["svc0"] = 2 },
		"pending migration": func(s *fingerprint.Structural) { s.PendingMigration["svc0"] = "edge02" },
		"edge capacity":     func(s *fingerprint.Structural) { s.EdgeCapacity["edge00"] = 180 },
		"transport drain":   func(s *fingerprint.Structural) { s.TransportQuiescence["drained:edge00:gw00"] = 9000 },
	}
	for name, mutate := range cases {
		b := base()
		mutate(&b)
		if a.Hash() == b.Hash() {
			t.Errorf("%s can change the future but does not change the fingerprint", name)
		}
	}
}

func containsSub(s, sub string) bool {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}

func TestHashStableAcrossMapOrder(t *testing.T) {
	a, b := base(), base()
	b.Routing = map[string]string{"gw01": "edge01", "gw00": "edge00"} // inserted differently
	if a.Hash() != b.Hash() {
		t.Fatal("hash depends on map iteration order; branch sets would abort at random")
	}
}

func TestFloatStateIsNotRoundedInsideExactHash(t *testing.T) {
	a, b := base(), base()
	b.RateTokens["gw00"] = a.RateTokens["gw00"] + 1e-9
	if a.Hash() == b.Hash() {
		t.Fatal("an exact fingerprint must not round distinct future-relevant float state")
	}
}

// The property the whole design rests on: a queue depth off by six is a
// different counterfactual starting state, and no tolerance may hide it.
func TestQueueDepthDifferenceIsFatal(t *testing.T) {
	a, b := base(), base()
	b.Queues["edge00"] = fingerprint.HashQueue(ids(1001, 54))
	if a.Hash() == b.Hash() {
		t.Fatal("queue depth is not part of the structural fingerprint")
	}
	d := a.Diff(b)
	if len(d) == 0 {
		t.Fatal("Diff must say which field disagreed")
	}
}

func TestEveryStructuralFieldMatters(t *testing.T) {
	a := base()
	cases := map[string]func(*fingerprint.Structural){
		"tick":      func(s *fingerprint.Structural) { s.LogicalTick = 121 },
		"config":    func(s *fingerprint.Structural) { s.ConfigHash = "other" },
		"fault":     func(s *fingerprint.Structural) { s.FaultPhase = "F1@0.13" },
		"routing":   func(s *fingerprint.Structural) { s.Routing["gw00"] = "edge02" },
		"rate":      func(s *fingerprint.Structural) { s.RateLimits["gw00"] = 0.9 },
		"seq":       func(s *fingerprint.Structural) { s.SeqPositions["gw00"] = 9002 },
		"processed": func(s *fingerprint.Structural) { s.ProcessedCounts["edge00"] = 40001 },
		"history":   func(s *fingerprint.Structural) { s.ActionHistory = []string{"NO_OP"} },
	}
	for name, mutate := range cases {
		b := base()
		mutate(&b)
		if a.Hash() == b.Hash() {
			t.Errorf("%s is not covered by the structural fingerprint", name)
		}
	}
}

func TestRuntimeStackIDChangesWithTransport(t *testing.T) {
	a := fingerprint.RuntimeStack{GoVersion: "go1.23", BusType: "stdlib-tcp", BusVersion: "a1a-1"}
	b := a
	b.BusType = "nats"
	if a.ID() == b.ID() {
		t.Fatal("changing the transport must invalidate the runtime stack id, " +
			"or an eta_J measured on one stack could be reported for another")
	}
}
