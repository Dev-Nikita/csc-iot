package rng

import "testing"

func TestDeriveIsDeterministic(t *testing.T) {
	if Derive(42, Mobility, 0) != Derive(42, Mobility, 0) {
		t.Fatal("same inputs must give the same seed")
	}
}

func TestStreamsAreIndependent(t *testing.T) {
	// The property that matters: consuming from one component must not change
	// what another component produces.
	s := New(42)
	fault := s.Get(Fault, 0)
	want := make([]float64, 5)
	for i := range want {
		want[i] = fault.Float64()
	}

	s2 := New(42)
	mob := s2.Get(Mobility, 0)
	for i := 0; i < 1000; i++ { // burn a lot of mobility draws
		mob.Float64()
	}
	fault2 := s2.Get(Fault, 0)
	for i := range want {
		if got := fault2.Float64(); got != want[i] {
			t.Fatalf("fault stream perturbed by mobility draws at %d: %v != %v", i, got, want[i])
		}
	}
}

func TestInstancesDiffer(t *testing.T) {
	if Derive(42, Workload, 0) == Derive(42, Workload, 1) {
		t.Fatal("instances must not collide")
	}
}

func TestMasterSeedChangesEverything(t *testing.T) {
	for _, c := range All() {
		if Derive(1, c, 0) == Derive(2, c, 0) {
			t.Fatalf("component %s ignored the master seed", c)
		}
	}
}
