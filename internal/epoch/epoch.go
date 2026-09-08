// Package epoch implements the logical anchor barrier.
//
// A replay branch must not be taken at an arbitrary wall-clock instant. If it
// were, the components would be at different points in their own work when the
// action landed, and the "same" prefix would mean different things in different
// branches. The barrier makes the anchor a logical event: the coordinator
// declares epoch k only once every participant has acknowledged completing all
// work belonging to ticks < k.
//
// This is deliberately the ONLY place where the system is synchronised. Message
// delivery is not globally reordered, and where queueing depends on arrival
// order that order is preserved -- reordering everything would erase the
// nondeterminism D0 exists to measure.
package epoch

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"slices"
	"sync"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
)

type ack struct {
	RunID       string `json:"run_id"`
	Epoch       int64  `json:"epoch"`
	Participant string `json:"participant"`
}

// declaration carries the run identity as well as the epoch number.
//
// Epochs restart at 1 on every orchestrator invocation while the nodes keep
// running, so an epoch number is not an identity: an acknowledgement or a drain
// confirmation left over from a previous invocation would answer the current
// one. The run id is what makes an anchor attributable to the run that took it.
type declaration struct {
	RunID string `json:"run_id"`
	Epoch int64  `json:"epoch"`
}

// NewRunID returns a fresh run identity: a UTC timestamp for legibility plus
// random bytes, so two runs started in the same second still differ.
func NewRunID() string {
	var b [6]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic("epoch: no entropy for a run id: " + err.Error())
	}
	return time.Now().UTC().Format("20060102T150405Z") + "-" + hex.EncodeToString(b[:])
}

// Coordinator declares epochs once all participants are ready.
type Coordinator struct {
	b            bus.Bus
	runID        string
	participants []string
	mu           sync.Mutex
	acks         map[int64]map[string]bool
	ready        map[int64]chan struct{}
}

func NewCoordinator(ctx context.Context, b bus.Bus, runID string, participants []string) (*Coordinator, error) {
	if runID == "" {
		return nil, fmt.Errorf("epoch: a coordinator needs a run id")
	}
	c := &Coordinator{
		b: b, runID: runID, participants: append([]string(nil), participants...),
		acks: map[int64]map[string]bool{}, ready: map[int64]chan struct{}{},
	}
	err := b.Subscribe(ctx, bus.SubjectEpochAck, func(e bus.Envelope) {
		var a ack
		if json.Unmarshal(e.Payload, &a) != nil {
			return
		}
		if a.RunID != c.runID {
			return // an acknowledgement belonging to another run
		}
		c.mu.Lock()
		defer c.mu.Unlock()
		if c.acks[a.Epoch] == nil {
			c.acks[a.Epoch] = map[string]bool{}
		}
		c.acks[a.Epoch][a.Participant] = true
		// Count only expected participants. Comparing sizes let one stray
		// acknowledgement -- a node left over from a previous branch, still on
		// the bus -- make the count exceed the expected number, so the barrier
		// timed out reporting that nobody was missing.
		if c.completeLocked(a.Epoch) {
			if ch, ok := c.ready[a.Epoch]; ok {
				close(ch)
				delete(c.ready, a.Epoch)
			}
		}
	})
	return c, err
}

func (c *Coordinator) completeLocked(k int64) bool {
	for _, p := range c.participants {
		if !c.acks[k][p] {
			return false
		}
	}
	return true
}

// Await blocks until every participant has acknowledged epoch k, or the
// deadline passes. A timeout is reported as such: a barrier that silently
// proceeds with a missing participant would produce branches whose prefixes
// were never equal, which is the failure this package exists to prevent.
func (c *Coordinator) Await(ctx context.Context, k int64, timeout time.Duration) error {
	c.mu.Lock()
	if c.completeLocked(k) {
		c.mu.Unlock()
		return nil
	}
	ch, ok := c.ready[k]
	if !ok {
		ch = make(chan struct{})
		c.ready[k] = ch
	}
	c.mu.Unlock()

	select {
	case <-ch:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(timeout):
		c.mu.Lock()
		missing := []string{}
		for _, p := range c.participants {
			if !c.acks[k][p] {
				missing = append(missing, p)
			}
		}
		c.mu.Unlock()
		var strays []string
		for p := range c.acks[k] {
			if !slices.Contains(c.participants, p) {
				strays = append(strays, p)
			}
		}
		if len(strays) > 0 {
			return fmt.Errorf("epoch %d barrier timed out; missing %v; "+
				"unexpected participants on the bus: %v (a previous run's processes?)",
				k, missing, strays)
		}
		return fmt.Errorf("epoch %d barrier timed out; no acknowledgement from %v", k, missing)
	}
}

// Declare broadcasts that epoch k has begun.
func (c *Coordinator) Declare(ctx context.Context, k int64) error {
	p, err := json.Marshal(declaration{RunID: c.runID, Epoch: k})
	if err != nil {
		return err
	}
	return c.b.Publish(ctx, bus.SubjectEpoch, bus.Envelope{
		LogicalTick: k, ProducerID: "coordinator", Subject: bus.SubjectEpoch, Payload: p,
	})
}

// Participant acknowledges completion of its own work per epoch.
//
// A participant does not choose the run it belongs to; it adopts the run id of
// whichever declaration it is answering and echoes it in the acknowledgement,
// so a late ack can never be counted towards a later run.
type Participant struct {
	b    bus.Bus
	id   string
	work func(runID string, epoch int64)
}

func NewParticipant(ctx context.Context, b bus.Bus, id string,
	work func(runID string, epoch int64)) (*Participant, error) {
	p := &Participant{b: b, id: id, work: work}
	err := b.Subscribe(ctx, bus.SubjectEpoch, func(e bus.Envelope) {
		var d declaration
		if json.Unmarshal(e.Payload, &d) != nil {
			return
		}
		if p.work != nil {
			p.work(d.RunID, d.Epoch)
		}
		_ = p.Ack(ctx, d.RunID, d.Epoch)
	})
	return p, err
}

func (p *Participant) Ack(ctx context.Context, runID string, k int64) error {
	payload, err := json.Marshal(ack{RunID: runID, Epoch: k, Participant: p.id})
	if err != nil {
		return err
	}
	return p.b.Publish(ctx, bus.SubjectEpochAck, bus.Envelope{
		LogicalTick: k, ProducerID: p.id, Subject: bus.SubjectEpochAck, Payload: payload,
	})
}
