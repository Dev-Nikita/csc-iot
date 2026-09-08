package replay_test

import (
	"testing"

	"github.com/TODO-OWNER/csc-iot/internal/config"
	"github.com/TODO-OWNER/csc-iot/internal/control"
	"github.com/TODO-OWNER/csc-iot/internal/faults"
	"github.com/TODO-OWNER/csc-iot/internal/replay"
	"github.com/TODO-OWNER/csc-iot/internal/sim"
)

func cfg(t *testing.T) config.Config {
	t.Helper()
	sc, _ := faults.ByID("F1", 40)
	c := config.Smoke(42, sc, "B1_threshold")
	c.Topology.Devices = 60
	c.Timing.WarmupS, c.Timing.MeasureS, c.Timing.CooldownS = 5, 30, 1
	return c
}

// The prefix must be identical across branches; only the anchor action differs.
func TestBranchesShareTheirPrefix(t *testing.T) {
	c := cfg(t)
	a := replay.NewAnchor(c, 12, []string{"NO_OP", "REROUTE"})
	b := replay.NewAnchor(c, 12, []string{"NO_OP", "REROUTE"})
	if a.StateID != b.StateID {
		t.Fatal("anchor is not reproducible from its own inputs")
	}
	if a.WorkloadHash == "" || a.FaultHash == "" {
		t.Fatal("anchor must fingerprint the workload and fault schedules")
	}
}

func TestBranchIDsAreDistinct(t *testing.T) {
	seen := map[string]bool{}
	for _, act := range []string{"NO_OP", "REROUTE", "THROTTLE"} {
		for rep := 0; rep < 3; rep++ {
			id := replay.BranchID("state", act, rep)
			if seen[id] {
				t.Fatalf("branch id collision for %s/%d", act, rep)
			}
			seen[id] = true
		}
	}
}

// Re-running the same branch must give the same numbers. Without this, nothing
// downstream -- eta_J, CRA, regret -- means anything.
func TestBranchIsReproducible(t *testing.T) {
	c := cfg(t)
	r1, err := sim.RunBranch(c, control.NewThreshold(), 8, sim.Reroute, "", 30)
	if err != nil {
		t.Fatal(err)
	}
	r2, err := sim.RunBranch(c, control.NewThreshold(), 8, sim.Reroute, "", 30)
	if err != nil {
		t.Fatal(err)
	}
	if r1.QueueFinal != r2.QueueFinal || r1.Retries != r2.Retries || r1.Failed != r2.Failed {
		t.Fatalf("branch not reproducible: %+v vs %+v", r1, r2)
	}
	if sim.Percentile(r1.Latencies, 99) != sim.Percentile(r2.Latencies, 99) {
		t.Fatal("branch p99 not reproducible")
	}
}

// Actions must reach system state. A branch that differs only by its label is
// worthless as a reference outcome.
func TestActionsReachSystemState(t *testing.T) {
	c := cfg(t)
	noop, err := sim.RunBranch(c, control.NewThreshold(), 8, sim.NoOp, "", 30)
	if err != nil {
		t.Fatal(err)
	}
	rr, err := sim.RunBranch(c, control.NewThreshold(), 8, sim.Reroute, "", 30)
	if err != nil {
		t.Fatal(err)
	}
	th, err := sim.RunBranch(c, control.NewThreshold(), 8, sim.Throttle, "", 30)
	if err != nil {
		t.Fatal(err)
	}
	if !rr.StateMutated {
		t.Error("REROUTE was dispatched but mutated no state")
	}
	if !th.StateMutated {
		t.Error("THROTTLE was dispatched but mutated no state")
	}
	if noop.StateMutated {
		t.Error("NO_OP mutated state")
	}
	if noop.Routes == rr.Routes {
		t.Error("REROUTE did not change the routing table")
	}
	if noop.Throttles == th.Throttles {
		t.Error("THROTTLE did not change the rate limiter")
	}
	if noop.Routes != th.Routes {
		t.Error("THROTTLE unexpectedly changed routing")
	}
}
