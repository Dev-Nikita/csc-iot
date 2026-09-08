// Package clock provides the experiment clock.
//
// Nothing in the simulation may branch on wall-clock time. Ordering, schedules
// and every scheduling decision are driven by ExperimentTime and Seq; the wall clock is
// recorded alongside for runtime performance measurement only. This is the
// precondition for replay: a run that consults time.Now() to decide anything
// cannot be reconstructed.
package clock

import (
	"sync/atomic"
	"time"
)

// Stamp is the triple attached to every event and telemetry sample.
type Stamp struct {
	ExperimentNanos int64  `json:"experiment_nanos"`
	Seq             uint64 `json:"seq"`
	WallNanos       int64  `json:"wall_nanos"`
}

// Clock advances in fixed ticks of experiment time.
type Clock struct {
	tick     time.Duration
	now      int64 // experiment nanoseconds
	seq      uint64
	wallBase time.Time
}

func New(tick time.Duration) *Clock {
	return &Clock{tick: tick, wallBase: time.Now()}
}

func (c *Clock) Tick() time.Duration { return c.tick }

// Advance moves experiment time forward by exactly one tick.
func (c *Clock) Advance() { atomic.AddInt64(&c.now, int64(c.tick)) }

// Now returns current experiment time in nanoseconds.
func (c *Clock) Now() int64 { return atomic.LoadInt64(&c.now) }

// Stamp issues a monotonically-sequenced stamp at the current experiment time.
func (c *Clock) Stamp() Stamp {
	return Stamp{
		ExperimentNanos: atomic.LoadInt64(&c.now),
		Seq:             atomic.AddUint64(&c.seq, 1) - 1,
		WallNanos:       time.Since(c.wallBase).Nanoseconds(),
	}
}

// Elapsed reports experiment time as a duration.
func (c *Clock) Elapsed() time.Duration { return time.Duration(c.Now()) }
