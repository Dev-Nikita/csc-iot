package sim_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/TODO-OWNER/csc-iot/internal/config"
	"github.com/TODO-OWNER/csc-iot/internal/control"
	"github.com/TODO-OWNER/csc-iot/internal/experiment"
	"github.com/TODO-OWNER/csc-iot/internal/faults"
	"github.com/TODO-OWNER/csc-iot/internal/sim"
	"github.com/TODO-OWNER/csc-iot/internal/telemetry"
)

func runOnce(t *testing.T, dir string, seed uint64, scenarioID string) (string, map[string]int64) {
	t.Helper()
	sc, ok := faults.ByID(scenarioID, 8)
	if !ok {
		t.Fatalf("unknown scenario %s", scenarioID)
	}
	ctrl := control.NewThreshold()
	cfg := config.Smoke(seed, sc, ctrl.Name())
	cfg.Topology.Devices = 40
	cfg.Timing.WarmupS, cfg.Timing.MeasureS, cfg.Timing.CooldownS = 2, 8, 1

	tw, err := telemetry.NewWriter(dir, "telemetry.jsonl")
	if err != nil {
		t.Fatal(err)
	}
	dw, err := telemetry.NewWriter(dir, "decisions.jsonl")
	if err != nil {
		t.Fatal(err)
	}
	eng, err := sim.New(cfg, ctrl)
	if err != nil {
		t.Fatal(err)
	}
	counters, err := eng.Run(tw, dw)
	if err != nil {
		t.Fatal(err)
	}
	if err := tw.Close(); err != nil {
		t.Fatal(err)
	}
	if err := dw.Close(); err != nil {
		t.Fatal(err)
	}
	// Wall-clock time is the one field legitimately allowed to differ between
	// two runs of the same seed; everything else must be identical.
	sum, err := experiment.DeterminismDigest(filepath.Join(dir, "decisions.jsonl"), "wall_nanos")
	if err != nil {
		t.Fatal(err)
	}
	return sum, counters
}

// The gate the whole replay contribution depends on: same seed, same outcome.
func TestSameSeedReproducesRun(t *testing.T) {
	a, ca := runOnce(t, filepath.Join(t.TempDir(), "a"), 42, "F1")
	b, cb := runOnce(t, filepath.Join(t.TempDir(), "b"), 42, "F1")
	if a != b {
		t.Fatalf("decision log differs across runs at the same seed:\n a=%s\n b=%s", a, b)
	}
	for k, v := range ca {
		if cb[k] != v {
			t.Fatalf("counter %s differs: %d != %d", k, v, cb[k])
		}
	}
}

func TestDifferentSeedsDiverge(t *testing.T) {
	a, _ := runOnce(t, filepath.Join(t.TempDir(), "a"), 42, "F1")
	b, _ := runOnce(t, filepath.Join(t.TempDir(), "b"), 43, "F1")
	if a == b {
		t.Fatal("different seeds produced an identical run: the seed is not reaching the workload")
	}
}

func TestScenarioChangesOutcome(t *testing.T) {
	_, f1 := runOnce(t, filepath.Join(t.TempDir(), "f1"), 42, "F1")
	_, f2 := runOnce(t, filepath.Join(t.TempDir(), "f2"), 42, "F2")
	if f1["retries"] == f2["retries"] {
		t.Fatal("F1 and F2 produced identical retry counts; the fault schedule is not biting")
	}
}

// Actions must change system state, not a cosmetic variable.
func TestFaultScheduleIsMonotoneInLoss(t *testing.T) {
	sc := faults.F1(10)
	s := faults.New(sc)
	prev := -1.0
	for _, at := range []float64{0, 2, 4, 6, 8, 10} {
		l := s.At(at, "all")
		if l.LossRatio < prev {
			t.Fatalf("F1 loss decreased at t=%v", at)
		}
		prev = l.LossRatio
	}
	if prev < 0.19 {
		t.Fatalf("F1 did not reach ~20%% loss, got %v", prev)
	}
}

func TestStateIDDependsOnHistory(t *testing.T) {
	a := sim.StateID("cfg", 42, 10, []string{"NO_OP"})
	b := sim.StateID("cfg", 42, 10, []string{"REROUTE"})
	if a == b {
		t.Fatal("state id ignores action history; branches could be confused")
	}
}

func TestMain(m *testing.M) { os.Exit(m.Run()) }
