package rpc_test

import (
	"context"
	"testing"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/rpc"
)

func req() rpc.StateRequest {
	return rpc.StateRequest{
		DecisionID: "d1", RunID: "r1", LogicalTick: 42,
		Features: map[string]float64{"queue": 12},
		Actions:  []string{"NO_OP", "REROUTE", "THROTTLE"},
	}
}

func TestRoundTripAndTimingSeparation(t *testing.T) {
	s, err := rpc.StartStub("127.0.0.1:0", 5*time.Millisecond)
	if err != nil {
		t.Fatal(err)
	}
	defer s.Close()
	c, err := rpc.DialFramed(s.Addr(), time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()

	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	resp, timing, err := c.EvaluateActions(ctx, req())
	if err != nil {
		t.Fatal(err)
	}
	if len(resp.Scores) != 3 {
		t.Fatalf("expected a score per action, got %d", len(resp.Scores))
	}
	if timing.ModelNanos == 0 {
		t.Fatal("model time must be reported separately from transport time")
	}
	if timing.DeadlineMissed {
		t.Fatal("a 5 ms stub must not miss a 1 s deadline")
	}
}

// The property the runtime budget depends on: a slow intelligence plane
// produces a recorded fallback, not a stalled controller.
func TestDeadlineMissBecomesAFallback(t *testing.T) {
	s, _ := rpc.StartStub("127.0.0.1:0", 400*time.Millisecond)
	defer s.Close()
	c, _ := rpc.DialFramed(s.Addr(), time.Second)
	defer c.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Millisecond)
	defer cancel()
	start := time.Now()
	_, timing, err := c.EvaluateActions(ctx, req())
	elapsed := time.Since(start)

	if err == nil {
		t.Fatal("a slow reply must surface as an error the controller can fall back from")
	}
	if !timing.DeadlineMissed {
		t.Fatal("timing must mark the deadline as missed")
	}
	if elapsed > 250*time.Millisecond {
		t.Fatalf("controller waited %v past its deadline", elapsed)
	}
}

func TestDescriptorDoesNotClaimGRPC(t *testing.T) {
	s, _ := rpc.StartStub("127.0.0.1:0", time.Millisecond)
	defer s.Close()
	c, _ := rpc.DialFramed(s.Addr(), time.Second)
	defer c.Close()
	if d := c.Descriptor(); d.Type != "stdlib-framed-tcp" {
		t.Fatalf("the development RPC must not describe itself as anything else, got %q", d.Type)
	}
}
