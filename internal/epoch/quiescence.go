package epoch

import (
	"context"
	"encoding/json"
	"fmt"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
)

// Quiescence closes the gap between "every participant finished its local work"
// and "the transport holds nothing belonging to the previous epoch".
//
// The plain barrier is not enough on an asynchronous bus. A gateway can
// truthfully acknowledge that it completed tick 99 while a message it published
// during tick 99 is still sitting in a socket buffer on its way to an edge. Both
// branches would then show identical local counters and differ in what is in
// flight -- a prefix mismatch that no amount of local bookkeeping can see, and
// which looks like a valid common anchor right up until the branches diverge for
// reasons nobody can account for.
//
// The protocol is a watermark, not a scheduler. Producers declare how far they
// got; consumers declare how far they have consumed. The anchor opens only when
// those agree for every (producer, consumer) pair. Within an epoch, messages are
// still delivered and processed in real arrival order: the goal is completeness,
// not determinism, and imposing an order here would erase what D0 measures.

// EndEpoch is a producer's declaration of its last sequence number in an epoch.
type EndEpoch struct {
	// RunID scopes the epoch. Epoch numbers restart at 1 on every orchestrator
	// invocation, so with long-lived nodes an epoch 4 from one run and an epoch 4
	// from the next collide in the same map. A saved anchor showed exactly that:
	// end:gw00 = 2000 with drained:edge00:gw00 = 1866, an accepted anchor over an
	// undrained transport.
	RunID      string `json:"run_id"`
	Epoch      int64  `json:"epoch"`
	ProducerID string `json:"producer_id"`
	Subject    string `json:"subject"`
	LastSeq    uint64 `json:"last_seq"`
}

// Drained is a consumer's confirmation of how far it has consumed a producer.
type Drained struct {
	RunID              string `json:"run_id"`
	Epoch              int64  `json:"epoch"`
	ProducerID         string `json:"producer_id"`
	ConsumerID         string `json:"consumer_id"`
	Subject            string `json:"subject"`
	ConsumedThroughSeq uint64 `json:"consumed_through_seq"`
}

const (
	SubjectEndEpoch = "experiment.epoch.end"
	SubjectDrained  = "experiment.epoch.drained"
)

// key is the identity of an epoch. Epoch numbers restart at 1 on every
// orchestrator invocation, so with long-lived nodes the epoch alone is not an
// identity: state from a previous run answers the current one.
type key struct {
	run   string
	epoch int64
}

// Watermark tracks end-of-epoch declarations and drain confirmations.
type Watermark struct {
	b bus.Bus
	// runID is the run this watermark speaks for. The orchestrator binds it at
	// construction and rejects anything from another run. A node passes "" and
	// becomes a follower: it adopts the run id of whichever declaration it is
	// answering and discards the state of the run it leaves, because residue
	// from a previous invocation is exactly what must not answer this one.
	runID    string
	follower bool
	// producers is the set of nodes that must close an epoch before it can be
	// read. Requiring only that DECLARED ends be drained made quiescence
	// transiently true: an epoch in which the idle gateway had declared and the
	// busy one had not yet was "quiescent" for as long as it took the second
	// declaration to arrive, and a fingerprint taken in that window recorded a
	// state nobody had finished producing.
	producers []string
	consumers []string
	// consumerFor names who is expected to drain a subject. Requiring every
	// participant to confirm every producer was wrong and produced a permanently
	// unquiescent system: a gateway does not subscribe to another gateway's work
	// and can never confirm it. Work is published to edge.work.<edgeID>, so the
	// subject names its own consumer.
	consumerFor func(subject string) []string

	mu      sync.Mutex
	ends    map[key]map[string]EndEpoch          // (run,epoch) -> producer -> declaration
	drained map[key]map[string]map[string]uint64 // (run,epoch) -> consumer -> producer -> seq
	ready   map[key]chan struct{}
}

// SubjectConsumer maps a per-edge work subject to the edge that drains it.
//
// It returns nil for anything else, and nil means "fall back to the declared
// consumer list". Splitting on the last dot unconditionally was wrong: the bare
// subject "edge.work" would resolve to a consumer literally named "work", which
// no node is, and quiescence could never be reached.
func SubjectConsumer(subject string) []string {
	prefix := bus.SubjectEdgeWork + "."
	if strings.HasPrefix(subject, prefix) && len(subject) > len(prefix) {
		return []string{subject[len(prefix):]}
	}
	return nil
}

func NewWatermark(ctx context.Context, b bus.Bus, runID string, consumers []string) (*Watermark, error) {
	return NewWatermarkWith(ctx, b, runID, consumers, SubjectConsumer)
}

// NewWatermarkWith lets a caller override how a subject maps to its consumers.
func NewWatermarkWith(ctx context.Context, b bus.Bus, runID string, consumers []string,
	consumerFor func(string) []string) (*Watermark, error) {
	w := &Watermark{
		b: b, runID: runID, follower: runID == "", consumers: append([]string(nil), consumers...), consumerFor: consumerFor,
		ends: map[key]map[string]EndEpoch{}, drained: map[key]map[string]map[string]uint64{},
		ready: map[key]chan struct{}{},
	}
	if err := b.Subscribe(ctx, SubjectEndEpoch, func(e bus.Envelope) {
		var d EndEpoch
		if json.Unmarshal(e.Payload, &d) != nil {
			return
		}
		w.mu.Lock()
		if !w.adoptLocked(d.RunID) {
			w.mu.Unlock()
			return // a declaration belonging to another run
		}
		k := key{d.RunID, d.Epoch}
		if w.ends[k] == nil {
			w.ends[k] = map[string]EndEpoch{}
		}
		if prev, ok := w.ends[k][d.ProducerID]; !ok || d.LastSeq > prev.LastSeq {
			w.ends[k][d.ProducerID] = d
		}
		w.signalLocked(k)
		w.mu.Unlock()
	}); err != nil {
		return nil, err
	}
	err := b.Subscribe(ctx, SubjectDrained, func(e bus.Envelope) {
		var d Drained
		if json.Unmarshal(e.Payload, &d) != nil {
			return
		}
		w.mu.Lock()
		if !w.adoptLocked(d.RunID) {
			w.mu.Unlock()
			return
		}
		k := key{d.RunID, d.Epoch}
		if w.drained[k] == nil {
			w.drained[k] = map[string]map[string]uint64{}
		}
		if w.drained[k][d.ConsumerID] == nil {
			w.drained[k][d.ConsumerID] = map[string]uint64{}
		}
		// Monotonic. An unconditional assignment let a late or duplicated
		// confirmation move a watermark BACKWARDS, so a set that had reached
		// quiescence could stop being quiescent after the check and before the
		// fingerprint was read -- which is how an anchor came to record
		// drained 1866 against end 2000.
		// The entry must exist even at zero -- an idle producer's end is
		// declared at sequence 0 and "confirmed nothing" is a different state
		// from "did not confirm" -- but it may only ever move forward.
		if prev, ok := w.drained[k][d.ConsumerID][d.ProducerID]; !ok || d.ConsumedThroughSeq > prev {
			w.drained[k][d.ConsumerID][d.ProducerID] = d.ConsumedThroughSeq
		}
		w.signalLocked(k)
		w.mu.Unlock()
	})
	return w, err
}

// DeclareEnd is called by a producer when it has published everything for epoch k.
// ExpectProducers names the nodes that must close every epoch. Without it,
// quiescence means only "everything declared has been drained", which is true
// before anything has been declared at all.
func (w *Watermark) ExpectProducers(producers []string) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.producers = append([]string(nil), producers...)
}

// SetRun binds a follower to a run. Called by a node when it begins the work of
// an epoch, before it declares an end or confirms a drain.
func (w *Watermark) SetRun(runID string) {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.adoptLocked(runID)
}

// RunID reports the run this watermark currently speaks for.
func (w *Watermark) RunID() string {
	w.mu.Lock()
	defer w.mu.Unlock()
	return w.runID
}

// adoptLocked reports whether runID is the run this watermark speaks for,
// adopting it first if this is a follower that has moved on to a new run. The
// state of the abandoned run is dropped rather than kept: it can only mislead.
func (w *Watermark) adoptLocked(runID string) bool {
	if runID == w.runID {
		return true
	}
	if !w.follower || runID == "" {
		return false
	}
	w.runID = runID
	w.ends = map[key]map[string]EndEpoch{}
	w.drained = map[key]map[string]map[string]uint64{}
	for _, ch := range w.ready {
		close(ch)
	}
	w.ready = map[key]chan struct{}{}
	return true
}

func (w *Watermark) DeclareEnd(ctx context.Context, k int64, producerID, subject string, lastSeq uint64) error {
	p, err := json.Marshal(EndEpoch{
		RunID: w.runID, Epoch: k, ProducerID: producerID, Subject: subject, LastSeq: lastSeq})
	if err != nil {
		return err
	}
	return w.b.Publish(ctx, SubjectEndEpoch, bus.Envelope{
		LogicalTick: k, ProducerID: producerID, Subject: SubjectEndEpoch, Payload: p,
	})
}

// ConfirmDrained is called by a consumer once it has processed everything it
// received from a producer for epoch k.
func (w *Watermark) ConfirmDrained(ctx context.Context, k int64, consumerID, producerID, subject string, through uint64) error {
	p, err := json.Marshal(Drained{
		RunID: w.runID, Epoch: k, ProducerID: producerID, ConsumerID: consumerID,
		Subject: subject, ConsumedThroughSeq: through,
	})
	if err != nil {
		return err
	}
	return w.b.Publish(ctx, SubjectDrained, bus.Envelope{
		LogicalTick: k, ProducerID: consumerID, Subject: SubjectDrained, Payload: p,
	})
}

// quiescentLocked reports whether every consumer has consumed every declaring
// producer through its declared last sequence number.
func (w *Watermark) quiescentLocked(k key) (bool, []string) {
	ends := w.ends[k]
	if len(ends) == 0 {
		return false, []string{"no producer has declared end-of-epoch"}
	}
	var pending []string
	for _, p := range w.producers {
		if _, ok := ends[p]; !ok {
			pending = append(pending, fmt.Sprintf("%s has not declared end-of-epoch", p))
		}
	}
	for producer, end := range ends {
		// Only the consumers of THIS subject are expected to confirm it.
		expect := w.consumerFor(end.Subject)
		if len(expect) == 0 {
			expect = w.consumers
		}
		for _, c := range expect {
			got, ok := w.drained[k][c][producer]
			if !ok {
				pending = append(pending, fmt.Sprintf("%s has not confirmed %s", c, producer))
				continue
			}
			if got < end.LastSeq {
				pending = append(pending,
					fmt.Sprintf("%s consumed %s through %d of %d", c, producer, got, end.LastSeq))
			}
		}
	}
	sort.Strings(pending)
	return len(pending) == 0, pending
}

func (w *Watermark) signalLocked(k key) {
	if ok, _ := w.quiescentLocked(k); !ok {
		return
	}
	if ch, exists := w.ready[k]; exists {
		close(ch)
		delete(w.ready, k)
	}
}

// AwaitQuiescent blocks until epoch k is drained everywhere, or reports exactly
// what is still outstanding. It never proceeds on a timeout: an anchor opened
// over an undrained transport is precisely the defect this protocol prevents.
func (w *Watermark) AwaitQuiescent(ctx context.Context, epoch int64, timeout time.Duration) error {
	k := key{w.runID, epoch}
	w.mu.Lock()
	if ok, _ := w.quiescentLocked(k); ok {
		w.mu.Unlock()
		return nil
	}
	ch, exists := w.ready[k]
	if !exists {
		ch = make(chan struct{})
		w.ready[k] = ch
	}
	w.mu.Unlock()

	select {
	case <-ch:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(timeout):
		w.mu.Lock()
		_, pending := w.quiescentLocked(k)
		w.mu.Unlock()
		return fmt.Errorf("run %s epoch %d not quiescent: %v", w.runID, epoch, pending)
	}
}

// TransportQuiescenceFingerprint is the second exact-match gate. Two branches
// may only start from prefixes whose transport was drained identically.
// TransportQuiescenceFingerprintVerified returns the watermarks AND re-checks
// quiescence from that exact snapshot.
//
// Checking quiescence and then reading the map are two moments, and an anchor
// must be justified by the numbers it actually records -- not by a check that
// passed some milliseconds earlier against values that have since moved. The
// saved anchor with drained 1866 against end 2000 is what a separated check and
// snapshot produce.
func (w *Watermark) TransportQuiescenceFingerprintVerified(epoch int64) (map[string]uint64, error) {
	k := key{w.runID, epoch}
	w.mu.Lock()
	defer w.mu.Unlock()

	out := map[string]uint64{}
	for producer, end := range w.ends[k] {
		out["end:"+producer] = end.LastSeq
	}
	for consumer, byProducer := range w.drained[k] {
		for producer, seq := range byProducer {
			out["drained:"+consumer+":"+producer] = seq
		}
	}
	if ok, pending := w.quiescentLocked(k); !ok {
		return out, fmt.Errorf("snapshot is not quiescent: %v", pending)
	}
	// Belt and braces against a consumer mapping that lets a pair through:
	// no recorded drain may sit below the producer end it answers.
	for producer, end := range w.ends[k] {
		for _, c := range w.consumerFor(end.Subject) {
			if got := w.drained[k][c][producer]; got < end.LastSeq {
				return out, fmt.Errorf(
					"snapshot records %s consumed %s through %d of %d",
					c, producer, got, end.LastSeq)
			}
		}
	}
	return out, nil
}
