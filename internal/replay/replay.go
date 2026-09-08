// Package replay reconstructs a run prefix and re-executes one decision anchor
// under each candidate action.
//
// Reconstruction, not snapshotting. Congestion windows, goroutine schedules,
// broker buffers and in-flight packets cannot be captured faithfully, so the
// run is rebuilt from its own inputs -- master seed, per-component streams,
// configuration, workload and fault schedules, and the action history before
// the anchor -- and only the action AT the anchor is replaced.
//
// Scope warning that must travel with every number this package produces: it
// currently drives the in-process core. Any dispersion measured here is a
// development diagnostic. The paper's eta_J must be measured after the
// distributed substrate exists, where concurrent scheduling and real transport
// introduce noise this core does not have.
package replay

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"

	"github.com/TODO-OWNER/csc-iot/internal/config"
	"github.com/TODO-OWNER/csc-iot/internal/rng"
	"github.com/TODO-OWNER/csc-iot/internal/sim"
)

// Anchor is everything needed to rebuild a run up to a decision point.
type Anchor struct {
	StateID       string   `json:"state_id"`
	ConfigHash    string   `json:"config_hash"`
	MasterSeed    uint64   `json:"master_seed"`
	Streams       []string `json:"rng_streams"`
	Tick          int      `json:"tick"`
	ActionHistory []string `json:"action_history"`
	WorkloadHash  string   `json:"workload_schedule_hash"`
	FaultHash     string   `json:"fault_schedule_hash"`
}

// Branch is one executed alternative.
type Branch struct {
	BranchID     string  `json:"branch_id"`
	StateID      string  `json:"state_id"`
	Action       string  `json:"action"`
	Repetition   int     `json:"repetition"`
	Executed     bool    `json:"action_executed"`
	StateMutated bool    `json:"state_mutated"`
	QueueFinal   int     `json:"queue_depth_final"`
	QueueMax     int     `json:"queue_depth_max"`
	Retries      int64   `json:"retries"`
	Delivered    int64   `json:"events_delivered"`
	P50Ms        float64 `json:"p50_latency_ms"`
	P95Ms        float64 `json:"p95_latency_ms"`
	P99Ms        float64 `json:"p99_latency_ms"`
	Failed       bool    `json:"sla_failed"`
	CostObs      float64 `json:"cost_observed"`
	Routes       string  `json:"routes_final"`
	Throttles    string  `json:"throttles_final"`
}

func hashStrings(prefix string, xs ...string) string {
	h := sha256.New()
	fmt.Fprint(h, prefix)
	for _, x := range xs {
		fmt.Fprintf(h, "%s;", x)
	}
	return hex.EncodeToString(h.Sum(nil))[:16]
}

// NewAnchor records a decision point for later reconstruction.
func NewAnchor(cfg config.Config, tick int, history []string) Anchor {
	streams := make([]string, 0, len(rng.All()))
	for _, c := range rng.All() {
		streams = append(streams, string(c))
	}
	sort.Strings(streams)
	fh := make([]string, 0, len(cfg.Scenario.Schedule))
	for _, st := range cfg.Scenario.Schedule {
		fh = append(fh, fmt.Sprintf("%.3f:%.4f:%.2f:%s", st.AtS, st.LossRatio, st.ExtraRTTMs, st.TargetLinks))
	}
	return Anchor{
		StateID:       sim.StateID(cfg.Hash(), cfg.MasterSeed, tick, history),
		ConfigHash:    cfg.Hash(),
		MasterSeed:    cfg.MasterSeed,
		Streams:       streams,
		Tick:          tick,
		ActionHistory: append([]string(nil), history...),
		WorkloadHash:  hashStrings("workload", fmt.Sprint(cfg.Topology.Devices), fmt.Sprint(cfg.EventRateHz)),
		FaultHash:     hashStrings("fault", fh...),
	}
}

// BranchID is content-addressed, so two branches can never be confused and a
// repetition is distinguishable from a different action.
func BranchID(stateID, action string, rep int) string {
	h := sha256.Sum256([]byte(stateID + "|" + action + "|" + fmt.Sprint(rep)))
	return hex.EncodeToString(h[:])[:32]
}
