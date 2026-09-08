//go:build nats

// NEEDS_LOCAL_VALIDATION.
//
// This file is excluded from the default build. The environment this project is
// developed in cannot reach the Go module proxy, so nats.go cannot be compiled,
// race-tested, or exercised for reconnect, ordering, slow consumers or shutdown
// here. Shipping it inside the normal build would make `go test ./...` pass on a
// machine that has never run a line of it.
//
// Build and test it where the modules are available:
//
//	go get github.com/nats-io/nats.go
//	go test -tags=nats -race ./internal/bus/
//
// Core pub/sub only, deliberately. JetStream would add persistence,
// acknowledgement, redelivery and replay semantics, all of which change the
// timing this project measures -- eta_J would then describe a different system.
// Durability is not part of the research question; adding it casually would
// contaminate the measurement.
package bus

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/nats-io/nats.go"
)

type natsBus struct {
	nc   *nats.Conn
	mu   sync.Mutex
	subs []*nats.Subscription
	desc Descriptor
}

// DialNATS connects to a NATS server and reports itself honestly in the
// descriptor, so a measurement can never be attributed to the wrong stack.
func DialNATS(url string, timeout time.Duration) (Bus, error) {
	nc, err := nats.Connect(url,
		nats.Timeout(timeout),
		nats.MaxReconnects(-1),
		nats.ReconnectWait(200*time.Millisecond),
	)
	if err != nil {
		return nil, fmt.Errorf("nats connect: %w", err)
	}
	return &natsBus{
		nc: nc,
		desc: Descriptor{
			Type:    "nats",
			Version: nc.ConnectedServerVersion(),
			Config: map[string]string{
				"url":            url,
				"client_version": nats.Version,
				"mode":           "core-pubsub",
				"jetstream":      "false",
			},
		},
	}, nil
}

func (n *natsBus) Publish(ctx context.Context, subject string, env Envelope) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
	}
	env.Subject = subject
	b, err := encodeEnvelope(env)
	if err != nil {
		return err
	}
	return n.nc.Publish(subject, b)
}

func (n *natsBus) Subscribe(ctx context.Context, subject string, h Handler) error {
	sub, err := n.nc.Subscribe(subject, func(m *nats.Msg) {
		env, err := decodeEnvelope(m.Data)
		if err != nil {
			return
		}
		h(env)
	})
	if err != nil {
		return err
	}
	n.mu.Lock()
	n.subs = append(n.subs, sub)
	n.mu.Unlock()
	// Flush before returning. NATS registers a subscription asynchronously, so a
	// publisher starting immediately after Subscribe can beat the registration
	// to the server and its first messages are simply never delivered. In an
	// epoch barrier that surfaces as a node "not acknowledging" -- a race that
	// reads exactly like a logic bug in the node.
	return n.nc.FlushTimeout(2 * time.Second)
}

func (n *natsBus) Close() error {
	n.mu.Lock()
	for _, s := range n.subs {
		_ = s.Unsubscribe()
	}
	n.mu.Unlock()
	if err := n.nc.FlushTimeout(2 * time.Second); err != nil {
		return err
	}
	n.nc.Close()
	return nil
}

func (n *natsBus) Descriptor() Descriptor { return n.desc }
