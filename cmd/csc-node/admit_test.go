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
