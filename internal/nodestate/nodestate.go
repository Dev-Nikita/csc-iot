// Package nodestate reports a node's contribution to the structural fingerprint.
//
// The fingerprint is assembled across processes, because no single process
// knows the system's state. Each node answers a request with its own slice --
// its queues by content, its rate-limiter levels, its sequence positions -- and
// the orchestrator combines them. A node that answered with a summary rather
// than the exact values would make the combined fingerprint useless without
// making it look wrong, so every field here is exact.
package nodestate

import (
	"context"
	"encoding/json"
	"sync"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
	"github.com/TODO-OWNER/csc-iot/internal/fingerprint"
)

const (
	SubjectRequest = "experiment.fingerprint.request"
	SubjectReport  = "experiment.fingerprint.report"
)

// Request asks every node for its state at a logical tick.
type Request struct {
	Epoch     int64  `json:"epoch"`
	RequestID string `json:"request_id"`
}

// Report is one node's slice of the structural state.
type Report struct {
	Epoch      int64              `json:"epoch"`
	RequestID  string             `json:"request_id"`
	NodeID     string             `json:"node_id"`
	Role       string             `json:"role"`
	Routing    map[string]string  `json:"routing,omitempty"`
	RateLimits map[string]float64 `json:"rate_limits,omitempty"`
	RateTokens map[string]float64 `json:"rate_tokens,omitempty"`
	// Queues by content, not by depth: two queues of equal length holding
	// different events have different futures.
	Queues          map[string]fingerprint.Queue `json:"queues,omitempty"`
	SeqPositions    map[string]uint64            `json:"seq_positions,omitempty"`
	ProcessedCounts map[string]int64             `json:"processed_counts,omitempty"`
	// EdgeCapacity is configured service capacity per epoch. It is structural:
	// it governs how the queue drains and therefore the future.
	EdgeCapacity map[string]float64 `json:"edge_capacity,omitempty"`
	// Observed carries measured OUTCOMES -- served counts, accumulated waiting
	// time, agreement violations. These are deliberately NOT part of the
	// structural fingerprint and never enter its hash: an outcome is what a
	// branch produced, and requiring two branches to agree on it would confuse
	// the state an action is applied to with the result of applying it.
	Observed map[string]float64 `json:"observed,omitempty"`
}

// Provider is implemented by each role to describe itself.
type Provider func(epoch int64) Report

// Serve answers fingerprint requests for the lifetime of ctx.
func Serve(ctx context.Context, b bus.Bus, nodeID, role string, p Provider) error {
	return b.Subscribe(ctx, SubjectRequest, func(e bus.Envelope) {
		var req Request
		if json.Unmarshal(e.Payload, &req) != nil {
			return
		}
		rep := p(req.Epoch)
		rep.Epoch, rep.RequestID, rep.NodeID, rep.Role = req.Epoch, req.RequestID, nodeID, role
		payload, err := json.Marshal(rep)
		if err != nil {
			return
		}
		_ = b.Publish(ctx, SubjectReport, bus.Envelope{
			LogicalTick: req.Epoch, ProducerID: nodeID,
			EventID: req.RequestID + ":" + nodeID, Payload: payload,
		})
	})
}

// Collector gathers reports until every expected node has answered.
type Collector struct {
	mu       sync.Mutex
	expected map[string]bool
	reports  map[string]Report
	done     chan struct{}
	reqID    string
}

func NewCollector(ctx context.Context, b bus.Bus, expected []string, reqID string) (*Collector, error) {
	c := &Collector{
		expected: map[string]bool{}, reports: map[string]Report{},
		done: make(chan struct{}), reqID: reqID,
	}
	for _, e := range expected {
		c.expected[e] = true
	}
	err := b.Subscribe(ctx, SubjectReport, func(e bus.Envelope) {
		var r Report
		if json.Unmarshal(e.Payload, &r) != nil || r.RequestID != c.reqID {
			return
		}
		c.mu.Lock()
		defer c.mu.Unlock()
		if !c.expected[r.NodeID] {
			return
		}
		c.reports[r.NodeID] = r
		if len(c.reports) == len(c.expected) {
			select {
			case <-c.done:
			default:
				close(c.done)
			}
		}
	})
	return c, err
}

func (c *Collector) Done() <-chan struct{} { return c.done }

// Missing names the nodes that never answered, so a timeout says who rather
// than only that it happened.
func (c *Collector) Missing() []string {
	c.mu.Lock()
	defer c.mu.Unlock()
	var out []string
	for id := range c.expected {
		if _, ok := c.reports[id]; !ok {
			out = append(out, id)
		}
	}
	return out
}

// Combine merges the per-node reports into one structural fingerprint.
// Keys are namespaced by node so two nodes cannot silently overwrite each
// other's entry -- a collision would make different states hash alike.
func (c *Collector) Combine(epoch int64, configHash, faultPhase string, history []string) fingerprint.Structural {
	c.mu.Lock()
	defer c.mu.Unlock()
	s := fingerprint.Structural{
		LogicalTick: epoch, ConfigHash: configHash, FaultPhase: faultPhase,
		Routing: map[string]string{}, RateLimits: map[string]float64{},
		RateTokens: map[string]float64{}, Queues: map[string]fingerprint.Queue{},
		SeqPositions: map[string]uint64{}, ProcessedCounts: map[string]int64{},
		ActionHistory: append([]string(nil), history...),
	}
	for id, r := range c.reports {
		for k, v := range r.Routing {
			s.Routing[id+"/"+k] = v
		}
		for k, v := range r.RateLimits {
			s.RateLimits[id+"/"+k] = v
		}
		for k, v := range r.RateTokens {
			s.RateTokens[id+"/"+k] = v
		}
		for k, v := range r.Queues {
			s.Queues[id+"/"+k] = v
		}
		for k, v := range r.SeqPositions {
			s.SeqPositions[id+"/"+k] = v
		}
		for k, v := range r.ProcessedCounts {
			s.ProcessedCounts[id+"/"+k] = v
		}
		for k, v := range r.EdgeCapacity {
			if s.EdgeCapacity == nil {
				s.EdgeCapacity = map[string]float64{}
			}
			s.EdgeCapacity[id+"/"+k] = v
		}
	}
	return s
}

// Observed returns the measured outcomes reported by the nodes, keyed
// node/metric. It is separate from Combine because these values must not reach
// fingerprint.Structural: they describe what happened, not the state from which
// it happened.
func (c *Collector) Observed() map[string]float64 {
	c.mu.Lock()
	defer c.mu.Unlock()
	out := map[string]float64{}
	for id, r := range c.reports {
		for k, v := range r.Observed {
			out[id+"/"+k] = v
		}
	}
	return out
}
