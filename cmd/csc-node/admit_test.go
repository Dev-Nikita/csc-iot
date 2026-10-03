package main

import "testing"

// The gateway's admission capacity has two independent limiters: the THROTTLE
// action the controller chose, and the D5 fault the operator suffers. They are
// held apart on purpose -- merging them would make a fault indistinguishable
// from a control -- and whichever is tighter binds.
//
// Both the epoch-boundary backlog drain and the live ingress path must ask this
// function. The ingress path once read the action's limiter alone, which under
// NO_OP is -1, so every arriving event was forwarded and a declared gateway
// fault changed nothing: the accounting audit reported "the declared gateway
// fault had no effect" on all 36 D5 branches of d45-pilot-v6.
func TestEffectiveAdmitCap(t *testing.T) {
	for _, c := range []struct {
		name          string
		action, fault int64
		want          int64
	}{
		{"neither limits", -1, -1, -1},
		{"only the action limits", 50, -1, 50},
		{"only the fault limits -- the NO_OP case that was broken", -1, 40, 40},
		{"the fault is tighter", 50, 40, 40},
		{"the action is tighter", 50, 80, 50},
		{"equal", 50, 50, 50},
		{"a fault that admits nothing", -1, 0, 0},
		{"an action that admits nothing", 0, 40, 0},
	} {
		if got := effectiveAdmitCap(c.action, c.fault); got != c.want {
			t.Errorf("%s: effectiveAdmitCap(%d, %d) = %d, want %d",
				c.name, c.action, c.fault, got, c.want)
		}
	}
}

// Which limiter is charged for a deferred event. The objective's cost term is
// the realised cost of the ACTION -- C(NO_OP) = 0 by definition -- and a
// gateway admission fault defers work under every action, NO_OP included.
// Charging the fault's share to the action gave a branch that intervened in no
// way a positive cost, contradicting the definition the manuscript states.
//
// This mirrors the attribution in the ingress path. On a tie the action is
// charged: at equal caps the action would have deferred the event by itself,
// and the conservative direction is the one that never flatters the method.
func chargedToFault(action, fault int64) bool {
	return fault >= 0 && (action < 0 || fault < action)
}

func TestDeferralAttribution(t *testing.T) {
	for _, c := range []struct {
		name          string
		action, fault int64
		wantFault     bool
	}{
		{"NO_OP under a gateway fault -- the case that broke C(NO_OP)=0", -1, 40, true},
		{"THROTTLE with a tighter fault", 50, 40, true},
		{"THROTTLE tighter than the fault", 50, 80, false},
		{"THROTTLE with no fault", 50, -1, false},
		{"equal caps go to the action", 50, 50, false},
		{"a fault admitting nothing under NO_OP", -1, 0, true},
	} {
		if got := chargedToFault(c.action, c.fault); got != c.wantFault {
			t.Errorf("%s: chargedToFault(%d, %d) = %v, want %v",
				c.name, c.action, c.fault, got, c.wantFault)
		}
	}
}
