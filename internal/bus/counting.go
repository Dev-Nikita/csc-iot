package bus

import (
	"context"
	"sync/atomic"
)

// Counting wraps a Bus and counts what it publishes, so the objective's
// BANDWIDTH cost component is a measurement rather than a zero.
//
// What is counted: the bytes of the encoded envelope, exactly as the codec
// produces them. What is NOT counted, and is therefore understated: transport
// framing, TCP/IP headers, retransmissions, and anything the broker adds. The
// figure is a lower bound on wire bytes and is reported as such. It is counted
// here rather than in each adapter so that the two adapters cannot disagree
// about what a byte is.
type Counting struct {
	Bus
	bytes atomic.Uint64
	msgs  atomic.Uint64
}

// Count wraps b. A nil Bus is returned unchanged so a caller need not branch.
func Count(b Bus) *Counting {
	if b == nil {
		return nil
	}
	return &Counting{Bus: b}
}

func (c *Counting) Publish(ctx context.Context, subject string, env Envelope) error {
	if body, err := encodeEnvelope(env); err == nil {
		c.bytes.Add(uint64(len(body)))
		c.msgs.Add(1)
	}
	return c.Bus.Publish(ctx, subject, env)
}

// BytesOut is the cumulative encoded size of everything published.
func (c *Counting) BytesOut() uint64 { return c.bytes.Load() }

// MessagesOut is the cumulative count of publishes.
func (c *Counting) MessagesOut() uint64 { return c.msgs.Load() }
