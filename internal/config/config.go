// Package config holds the run configuration and its content hash.
//
// The hash goes into the manifest and into every replay anchor id, so a result
// can never be silently attributed to a configuration that did not produce it.
package config

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
)

type Topology struct {
	Devices  int `json:"devices"`
	Gateways int `json:"gateways"`
	Edges    int `json:"edges"`
}

type SLA struct {
	MaxE2ELatencyMs    float64 `json:"max_e2e_latency_ms"`
	MinDeliveryRatio   float64 `json:"min_delivery_ratio"`
	ViolationHoldTicks int     `json:"violation_hold_ticks"`
}

type Timing struct {
	TickMs      int `json:"tick_ms"`
	TelemetryMs int `json:"telemetry_ms"`
	WarmupS     int `json:"warmup_s"`
	MeasureS    int `json:"measure_s"`
	CooldownS   int `json:"cooldown_s"`
}

// FaultStep is one entry of a deterministic impairment schedule.
type FaultStep struct {
	AtS         float64 `json:"at_s"`
	LossRatio   float64 `json:"loss_ratio"`
	ExtraRTTMs  float64 `json:"extra_rtt_ms"`
	JitterMs    float64 `json:"jitter_ms"`
	TargetLinks string  `json:"target_links"` // "all" or a gateway id
}

type Scenario struct {
	ID       string      `json:"id"`
	Name     string      `json:"name"`
	Schedule []FaultStep `json:"schedule"`
}

type Config struct {
	ExperimentID   string   `json:"experiment_id"`
	MasterSeed     uint64   `json:"master_seed"`
	Controller     string   `json:"controller"`
	Topology       Topology `json:"topology"`
	SLA            SLA      `json:"sla"`
	Timing         Timing   `json:"timing"`
	Scenario       Scenario `json:"scenario"`
	EventRateHz    float64  `json:"event_rate_hz"`
	EdgeCapacityHz float64  `json:"edge_capacity_hz"`
	QueueLimit     int      `json:"queue_limit"`
	// ImpairmentMode records how degradation was applied. Reported results must
	// use "kernel_netem"; "application_layer" runs are labelled, never mixed in.
	ImpairmentMode string `json:"impairment_mode"`
}

// Hash is the sha256 of the canonical JSON encoding, minus the experiment id
// (which names the run, and must not change the identity of its configuration).
func (c Config) Hash() string {
	c2 := c
	c2.ExperimentID = ""
	b, err := json.Marshal(c2)
	if err != nil {
		panic(fmt.Sprintf("config is not serialisable: %v", err))
	}
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func (c Config) Validate() error {
	switch {
	case c.Topology.Devices <= 0:
		return fmt.Errorf("devices must be positive")
	case c.Topology.Gateways <= 0:
		return fmt.Errorf("gateways must be positive")
	case c.Topology.Edges <= 0:
		return fmt.Errorf("edges must be positive")
	case c.Timing.TickMs <= 0:
		return fmt.Errorf("tick_ms must be positive")
	case c.ImpairmentMode != "kernel_netem" && c.ImpairmentMode != "application_layer":
		return fmt.Errorf("impairment_mode must be kernel_netem or application_layer, got %q", c.ImpairmentMode)
	}
	return nil
}

func Load(path string) (Config, error) {
	var c Config
	b, err := os.ReadFile(path)
	if err != nil {
		return c, err
	}
	if err := json.Unmarshal(b, &c); err != nil {
		return c, err
	}
	return c, c.Validate()
}

// Smoke is the configuration behind `make experiment-smoke`.
func Smoke(seed uint64, scenario Scenario, controller string) Config {
	return Config{
		ExperimentID: fmt.Sprintf("%s-%s-seed%03d", scenario.ID, controller, seed),
		MasterSeed:   seed,
		Controller:   controller,
		// Three gateways, not two: with two, the round-robin map leaves edge02
		// idle and the baseline runs at 1.25x capacity before any fault is
		// injected. M2 found this -- every branch was already saturated, so most
		// anchors were insensitive to the action under test.
		Topology:       Topology{Devices: 100, Gateways: 3, Edges: 3},
		SLA:            SLA{MaxE2ELatencyMs: 250, MinDeliveryRatio: 0.98, ViolationHoldTicks: 4},
		Timing:         Timing{TickMs: 500, TelemetryMs: 100, WarmupS: 10, MeasureS: 60, CooldownS: 5},
		Scenario:       scenario,
		EventRateHz:    4,
		EdgeCapacityHz: 160,
		QueueLimit:     2000,
		ImpairmentMode: "application_layer",
	}
}
