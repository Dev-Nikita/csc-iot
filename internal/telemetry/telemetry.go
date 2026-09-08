// Package telemetry records timestamped samples and decisions as JSONL.
//
// Raw output is append-only. Nothing here rewrites a record, and the analysis
// pipeline derives everything it reports from these files.
package telemetry

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"sync"

	"github.com/TODO-OWNER/csc-iot/internal/clock"
)

// Sample is one telemetry observation of one vertex.
type Sample struct {
	Stamp    clock.Stamp `json:"stamp"`
	NodeID   string      `json:"node_id"`
	NodeType string      `json:"node_type"` // device | gateway | link | edge | service

	// network
	RTTMs       float64 `json:"rtt_ms,omitempty"`
	JitterMs    float64 `json:"jitter_ms,omitempty"`
	LossRatio   float64 `json:"loss_ratio,omitempty"`
	RetryRate   float64 `json:"retry_rate,omitempty"`
	LinkQuality float64 `json:"link_quality,omitempty"`

	// edge
	Load          float64 `json:"load,omitempty"`
	QueueDepth    int     `json:"queue_depth,omitempty"`
	ServiceTimeMs float64 `json:"service_time_ms,omitempty"`
	TimeoutRate   float64 `json:"timeout_rate,omitempty"`

	// application
	EventRateHz   float64 `json:"event_rate_hz,omitempty"`
	DeliveryRatio float64 `json:"delivery_ratio,omitempty"`
	E2ELatencyMs  float64 `json:"e2e_latency_ms,omitempty"`
	SLAViolation  bool    `json:"sla_violation,omitempty"`
}

// Decision is one controller tick: what it saw, what it did, and why.
type Decision struct {
	Stamp        clock.Stamp `json:"stamp"`
	DecisionID   string      `json:"decision_id"`
	StateID      string      `json:"state_id"`
	Controller   string      `json:"controller"`
	Action       string      `json:"action"`
	Target       string      `json:"target"`
	Executed     bool        `json:"action_executed"`
	StateMutated bool        `json:"state_mutated"`
	Abstained    bool        `json:"abstained"`
	Fallback     bool        `json:"fallback"`
	ObservedRisk float64     `json:"observed_risk"`
	Note         string      `json:"note,omitempty"`
}

// Writer serialises records to newline-delimited JSON.
type Writer struct {
	mu  sync.Mutex
	f   *os.File
	bw  *bufio.Writer
	enc *json.Encoder
}

func NewWriter(dir, name string) (*Writer, error) {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, err
	}
	f, err := os.Create(filepath.Join(dir, name))
	if err != nil {
		return nil, err
	}
	bw := bufio.NewWriterSize(f, 1<<20)
	return &Writer{f: f, bw: bw, enc: json.NewEncoder(bw)}, nil
}

func (w *Writer) Write(v any) error {
	w.mu.Lock()
	defer w.mu.Unlock()
	return w.enc.Encode(v)
}

func (w *Writer) Close() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if err := w.bw.Flush(); err != nil {
		w.f.Close()
		return err
	}
	return w.f.Close()
}
