// Package control holds the Phase A0 baseline controller.
//
// B1 is deliberately simple -- fixed thresholds, no model, no calibration --
// but it must not be deliberately crippled. The first version had no release
// rule: it entered a throttle and never left, firing 92 times and applying
// once. Comparing CSC against a baseline that cannot recover would flatter CSC
// for a reason that has nothing to do with counterfactual reasoning, and a
// reviewer would be right to discount the whole comparison. Hence hysteresis.
package control

import (
	"math/rand"

	"github.com/TODO-OWNER/csc-iot/internal/sim"
)

// Threshold is a reactive controller with enter/release hysteresis.
//
// It has the SAME action primitives available to it as the proposed controller.
// A baseline restricted to a poorer action set would let CSC win on repertoire
// rather than on decision quality, and a reviewer would be right to discount the
// comparison. What B1 lacks is not actions but a model: it maps an observed
// symptom to a fixed response by deterministic priority.
//
//	network impairment  -> throttle the source
//	compute overload    -> reroute to another edge
//	node unavailable    -> activate a replica   (once REPLICATE exists)
//
// All thresholds are frozen on validation/pilot data before comparative runs and
// never tuned against test outcomes.
type Threshold struct {
	QueueHigh    float64 // enter: load above this
	QueueLow     float64 // release: load below this (QueueLow < QueueHigh)
	LossHigh     float64
	LossLow      float64
	LatencyHigh  float64
	EnterTicks   int // consecutive ticks above the enter threshold
	ReleaseTicks int // consecutive ticks below the release threshold

	overCount  int
	underCount int
	throttled  map[string]bool
}

func NewThreshold() *Threshold {
	return &Threshold{
		QueueHigh: 0.35, QueueLow: 0.15,
		LossHigh: 0.12, LossLow: 0.05,
		LatencyHigh: 200,
		EnterTicks:  2, ReleaseTicks: 4,
		throttled: map[string]bool{},
	}
}

func (t *Threshold) Name() string { return "B1_threshold" }

// Decide returns an action, its target, and the scalar the rule fired on.
// That scalar is an OBSERVED quantity, not a predicted risk: B1 has no model,
// and calling it "risk" in the logs would blur the distinction the paper rests
// on.
func (t *Threshold) Decide(v sim.View, _ *rand.Rand) (sim.Action, string, float64) {
	busiest, maxLoad := "", -1.0
	for _, id := range v.Edges {
		if v.Load[id] > maxLoad {
			busiest, maxLoad = id, v.Load[id]
		}
	}
	if len(v.Gateways) == 0 {
		return sim.NoOp, "", maxLoad
	}
	gw := v.Gateways[0]

	// --- release path: only after the system has been calm for a while -----
	stressed := v.LossRatio > t.LossLow || maxLoad > t.QueueLow || v.E2ELatencyMs > t.LatencyHigh
	if stressed {
		t.underCount = 0
	} else {
		t.underCount++
	}
	if t.underCount >= t.ReleaseTicks {
		for g, on := range t.throttled {
			if on {
				t.throttled[g] = false
				return sim.Release, g, maxLoad
			}
		}
	}

	// --- enter path --------------------------------------------------------
	if v.LossRatio > t.LossHigh || maxLoad > t.QueueHigh || v.E2ELatencyMs > t.LatencyHigh {
		t.overCount++
	} else {
		t.overCount = 0
	}
	if t.overCount < t.EnterTicks {
		return sim.NoOp, "", maxLoad
	}

	if v.LossRatio > t.LossHigh && !t.throttled[gw] {
		t.throttled[gw] = true
		return sim.Throttle, gw, v.LossRatio
	}
	if maxLoad > t.QueueHigh || v.E2ELatencyMs > t.LatencyHigh {
		for _, g := range v.Gateways {
			if v.Routes[g] == busiest {
				gw = g
				break
			}
		}
		return sim.Reroute, gw, maxLoad
	}
	return sim.NoOp, "", maxLoad
}
