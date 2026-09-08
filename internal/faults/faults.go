// Package faults holds the deterministic impairment schedules F1 and F2.
//
// Schedules are pure functions of experiment time, never of wall clock and
// never of a live random draw: the same seed and the same configuration must
// produce the same degradation at the same tick, or replay is meaningless.
package faults

import "github.com/TODO-OWNER/csc-iot/internal/config"

// Link carries the impairment currently in force on a path.
type Link struct {
	LossRatio  float64
	ExtraRTTMs float64
	JitterMs   float64
}

// Schedule resolves impairment at a given experiment time by holding the last
// step at or before it. Steps between points are held, not interpolated, so
// that a run is reproducible from the step list alone.
type Schedule struct{ steps []config.FaultStep }

func New(sc config.Scenario) *Schedule { return &Schedule{steps: sc.Schedule} }

func (s *Schedule) At(elapsedS float64, gatewayID string) Link {
	var cur Link
	for _, st := range s.steps {
		if st.AtS > elapsedS {
			break
		}
		if st.TargetLinks != "all" && st.TargetLinks != gatewayID {
			continue
		}
		cur = Link{LossRatio: st.LossRatio, ExtraRTTMs: st.ExtraRTTMs, JitterMs: st.JitterMs}
	}
	return cur
}

// F1 is gradual link degradation: loss climbs 0 -> 20% over the ramp.
func F1(rampS float64) config.Scenario {
	steps := make([]config.FaultStep, 0, 11)
	for i := 0; i <= 10; i++ {
		steps = append(steps, config.FaultStep{
			AtS:         rampS * float64(i) / 10,
			LossRatio:   0.20 * float64(i) / 10,
			TargetLinks: "all",
		})
	}
	return config.Scenario{ID: "F1", Name: "gradual link degradation", Schedule: steps}
}

// F2 is latency inflation: RTT climbs 10 -> 250 ms over the ramp, with jitter
// scaling alongside it.
func F2(rampS float64) config.Scenario {
	steps := make([]config.FaultStep, 0, 11)
	for i := 0; i <= 10; i++ {
		extra := 240 * float64(i) / 10
		steps = append(steps, config.FaultStep{
			AtS:         rampS * float64(i) / 10,
			ExtraRTTMs:  extra,
			JitterMs:    extra * 0.1,
			TargetLinks: "all",
		})
	}
	return config.Scenario{ID: "F2", Name: "latency inflation", Schedule: steps}
}

// ByID resolves a scenario name for the CLI.
func ByID(id string, rampS float64) (config.Scenario, bool) {
	switch id {
	case "F1":
		return F1(rampS), true
	case "F2":
		return F2(rampS), true
	}
	return config.Scenario{}, false
}
