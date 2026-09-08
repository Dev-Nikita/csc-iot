// Package fingerprint captures the state a replay branch set must share.
//
// Two fingerprints, and the distinction between them is load-bearing.
//
// StructuralStateFingerprint is semantic and must match EXACTLY before a branch
// set is allowed to proceed. If branches were permitted to start from, say,
// queue depths of 48 and 54, then the dispersion band measured afterwards would
// mix runtime nondeterminism following the action -- which is what it must
// capture -- with pre-action state mismatch, which is not. The band would then
// be partly a measure of its own sloppiness, and every downstream comparison
// resolved against it would inherit that.
//
// RuntimeObservationFingerprint covers quantities that legitimately vary --
// CPU, memory, wall-clock timings. Its dispersion is recorded as evidence about
// the environment; it never gates branching.
package fingerprint

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"math"
	"sort"
)

// Structural is the exact-match semantic state at an anchor.
// Queue captures a queue's identity, not merely its size.
//
// Depth alone is not enough, and the failure is subtle: two prefixes holding
// [e1001..e1048] and [e1002..e1049] both report 48, and a fingerprint built on
// counters would call them equal. Their futures are different. That is worse
// than ordinary nondeterminism, because it presents as a valid common anchor
// and the divergence surfaces later with nothing to attribute it to.
type Queue struct {
	Length      int    `json:"length"`
	ContentHash string `json:"content_hash"` // SHA256 over the ordered event ids
	HeadEventID string `json:"head_event_id"`
	TailEventID string `json:"tail_event_id"`
}

// HashQueue builds a Queue from the ordered event ids it holds.
func HashQueue(eventIDs []string) Queue {
	q := Queue{Length: len(eventIDs)}
	if len(eventIDs) > 0 {
		q.HeadEventID, q.TailEventID = eventIDs[0], eventIDs[len(eventIDs)-1]
	}
	h := sha256.New()
	for _, id := range eventIDs {
		fmt.Fprintf(h, "%s\x00", id)
	}
	q.ContentHash = hex.EncodeToString(h.Sum(nil))[:32]
	return q
}

// RetryState is future-relevant and invisible in queue depth.
type RetryState struct {
	PendingHash    string           `json:"pending_hash"`
	AttemptCounts  map[string]int   `json:"attempt_counts"`
	BackoffDueTick map[string]int64 `json:"backoff_due_tick"` // logical time, never wall clock
}

// Structural is the exact-match semantic state at an anchor.
//
// Every field here is future-relevant: two prefixes agreeing on all of them
// should evolve identically under the same action. A field that can change the
// future while leaving the hash unchanged is a hole in the methodology, not a
// detail.
type Structural struct {
	LogicalTick int64             `json:"logical_tick"`
	ConfigHash  string            `json:"config_hash"`
	Routing     map[string]string `json:"routing"`
	// Configured limits AND the live token-bucket level: a limiter refilled to
	// 3 tokens behaves differently from one at 47 under the same configured rate.
	RateLimits       map[string]float64    `json:"rate_limits"`
	RateTokens       map[string]float64    `json:"rate_tokens"`
	Queues           map[string]Queue      `json:"queues"`
	Retries          map[string]RetryState `json:"retries"`
	TimeoutDueTick   map[string]int64      `json:"timeout_due_tick"`
	ServicePlacement map[string]string     `json:"service_placement"`
	ReplicaState     map[string]int        `json:"replica_state"`
	PendingMigration map[string]string     `json:"pending_migration"`
	EdgeCapacity     map[string]float64    `json:"edge_capacity"`
	SeqPositions     map[string]uint64     `json:"seq_positions"`
	ProcessedCounts  map[string]int64      `json:"processed_counts"`
	FaultPhase       string                `json:"fault_phase"`
	ActionHistory    []string              `json:"action_history"`
	// TransportQuiescence is the second exact gate: epoch watermarks proving
	// nothing from the previous epoch is still in flight.
	TransportQuiescence map[string]uint64 `json:"transport_quiescence"`
}

// Hash is order-independent over maps and stable across processes.
func (s Structural) Hash() string {
	h := sha256.New()
	fmt.Fprintf(h, "tick=%d|cfg=%s|fault=%s|", s.LogicalTick, s.ConfigHash, s.FaultPhase)
	writeStrMap(h, "route", s.Routing)
	writeF64Map(h, "rate", s.RateLimits)
	writeF64Map(h, "tokens", s.RateTokens)
	writeQueueMap(h, "queue", s.Queues)
	writeRetryMap(h, "retry", s.Retries)
	writeI64Map(h, "timeout", s.TimeoutDueTick)
	writeStrMap(h, "place", s.ServicePlacement)
	writeIntMap(h, "replica", s.ReplicaState)
	writeStrMap(h, "migrating", s.PendingMigration)
	writeF64Map(h, "cap", s.EdgeCapacity)
	writeU64Map(h, "seq", s.SeqPositions)
	writeI64Map(h, "proc", s.ProcessedCounts)
	writeU64Map(h, "quiesce", s.TransportQuiescence)
	for _, a := range s.ActionHistory {
		fmt.Fprintf(h, "act=%s;", a)
	}
	return hex.EncodeToString(h.Sum(nil))
}

// Diff reports the first fields that disagree, so an aborted branch set can say
// why rather than only that it failed.
func (s Structural) Diff(o Structural) []string {
	var d []string
	if s.LogicalTick != o.LogicalTick {
		d = append(d, fmt.Sprintf("logical_tick %d != %d", s.LogicalTick, o.LogicalTick))
	}
	if s.ConfigHash != o.ConfigHash {
		d = append(d, "config_hash differs")
	}
	if s.FaultPhase != o.FaultPhase {
		d = append(d, fmt.Sprintf("fault_phase %q != %q", s.FaultPhase, o.FaultPhase))
	}
	for k, v := range s.Routing {
		if o.Routing[k] != v {
			d = append(d, fmt.Sprintf("routing[%s] %s != %s", k, v, o.Routing[k]))
		}
	}
	for k, v := range s.Queues {
		ov := o.Queues[k]
		switch {
		case v.Length != ov.Length:
			d = append(d, fmt.Sprintf("queue[%s] length %d != %d", k, v.Length, ov.Length))
		case v.ContentHash != ov.ContentHash:
			d = append(d, fmt.Sprintf("queue[%s] same length %d but different contents (head %s vs %s)",
				k, v.Length, v.HeadEventID, ov.HeadEventID))
		}
	}
	for k, v := range s.Retries {
		if o.Retries[k].PendingHash != v.PendingHash {
			d = append(d, fmt.Sprintf("retry[%s] pending set differs", k))
		}
	}
	for k, v := range s.RateTokens {
		if o.RateTokens[k] != v {
			d = append(d, fmt.Sprintf("rate_tokens[%s] %.3f != %.3f", k, v, o.RateTokens[k]))
		}
	}
	for k, v := range s.TransportQuiescence {
		if o.TransportQuiescence[k] != v {
			d = append(d, fmt.Sprintf("transport_quiescence[%s] %d != %d", k, v, o.TransportQuiescence[k]))
		}
	}
	for k, v := range s.SeqPositions {
		if o.SeqPositions[k] != v {
			d = append(d, fmt.Sprintf("seq[%s] %d != %d", k, v, o.SeqPositions[k]))
		}
	}
	for k, v := range s.ProcessedCounts {
		if o.ProcessedCounts[k] != v {
			d = append(d, fmt.Sprintf("processed[%s] %d != %d", k, v, o.ProcessedCounts[k]))
		}
	}
	if len(s.ActionHistory) != len(o.ActionHistory) {
		d = append(d, "action_history length differs")
	}
	sort.Strings(d)
	return d
}

// RuntimeObservation records what may vary. It is evidence, never a gate.
type RuntimeObservation struct {
	CPUPercent    float64 `json:"cpu_percent"`
	RSSBytes      uint64  `json:"rss_bytes"`
	WallLatencyMs float64 `json:"wall_latency_ms"`
	GoroutineN    int     `json:"goroutines"`
}

// RuntimeStack identifies everything eta_J is a property of. Changing any field
// invalidates a measured resolution band: transport, buffering and scheduling
// all shape it, so a band measured on one stack does not transfer to another.
type RuntimeStack struct {
	GoVersion       string            `json:"go_version"`
	Kernel          string            `json:"kernel"`
	BusType         string            `json:"bus_type"`
	BusVersion      string            `json:"bus_version"`
	TransportHash   string            `json:"transport_config_hash"`
	RPCType         string            `json:"rpc_type"`
	ProcessTopology string            `json:"process_topology"`
	Images          map[string]string `json:"container_images"`
	NetemConfig     string            `json:"netem_config"`
}

// ID is the value recorded beside every eta_J.
func (r RuntimeStack) ID() string {
	h := sha256.New()
	fmt.Fprintf(h, "%s|%s|%s|%s|%s|%s|%s|%s|",
		r.GoVersion, r.Kernel, r.BusType, r.BusVersion,
		r.TransportHash, r.RPCType, r.ProcessTopology, r.NetemConfig)
	writeStrMap(h, "img", r.Images)
	return hex.EncodeToString(h.Sum(nil))[:16]
}

func writeStrMap(h interface{ Write([]byte) (int, error) }, tag string, m map[string]string) {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		fmt.Fprintf(h, "%s[%s]=%s;", tag, k, m[k])
	}
}

func writeIntMap(h interface{ Write([]byte) (int, error) }, tag string, m map[string]int) {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		fmt.Fprintf(h, "%s[%s]=%d;", tag, k, m[k])
	}
}

func writeI64Map(h interface{ Write([]byte) (int, error) }, tag string, m map[string]int64) {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		fmt.Fprintf(h, "%s[%s]=%d;", tag, k, m[k])
	}
}

func writeU64Map(h interface{ Write([]byte) (int, error) }, tag string, m map[string]uint64) {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		fmt.Fprintf(h, "%s[%s]=%d;", tag, k, m[k])
	}
}

func writeF64Map(h interface{ Write([]byte) (int, error) }, tag string, m map[string]float64) {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		// Exact IEEE-754 bits. Decimal rounding silently introduced a tolerance
		// into a fingerprint described as exact: values differing below 1e-6
		// could start different futures while producing the same anchor hash.
		v := m[k]
		if v == 0 {
			v = 0 // canonicalise negative zero, which is semantically identical
		}
		fmt.Fprintf(h, "%s[%s]=%016x;", tag, k, math.Float64bits(v))
	}
}

func writeQueueMap(h interface{ Write([]byte) (int, error) }, tag string, m map[string]Queue) {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		q := m[k]
		fmt.Fprintf(h, "%s[%s]=%d:%s:%s:%s;", tag, k, q.Length, q.ContentHash, q.HeadEventID, q.TailEventID)
	}
}

func writeRetryMap(h interface{ Write([]byte) (int, error) }, tag string, m map[string]RetryState) {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		r := m[k]
		fmt.Fprintf(h, "%s[%s]=%s;", tag, k, r.PendingHash)
		writeIntMap(h, tag+".attempts["+k+"]", r.AttemptCounts)
		writeI64Map(h, tag+".backoff["+k+"]", r.BackoffDueTick)
	}
}
