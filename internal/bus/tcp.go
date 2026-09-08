package bus

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"sync"
	"time"
)

// tcpBroker is a minimal publish/subscribe broker over stdlib TCP.
//
// It is a DEVELOPMENT transport. It exists so the distributed semantics --
// separate processes, real sockets, real interleaving -- can be built and tested
// where the module proxy is unreachable. It is not NATS and must never be
// described as NATS in a manifest or in the manuscript.
type tcpBroker struct {
	ln     net.Listener
	mu     sync.RWMutex
	subs   map[string]map[*conn]struct{}
	conns  map[*conn]struct{}
	wg     sync.WaitGroup
	closed chan struct{}
	once   sync.Once
}

type conn struct {
	c   net.Conn
	enc *json.Encoder
	mu  sync.Mutex
}

func (c *conn) send(f frame) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.enc.Encode(f)
}

type frame struct {
	Kind    string   `json:"kind"` // "sub" | "pub"
	Subject string   `json:"subject,omitempty"`
	Env     Envelope `json:"env,omitempty"`
}

// StartBroker listens on addr and serves until Close.
func StartBroker(addr string) (*tcpBroker, error) {
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return nil, err
	}
	b := &tcpBroker{
		ln: ln, subs: map[string]map[*conn]struct{}{},
		conns: map[*conn]struct{}{}, closed: make(chan struct{}),
	}
	b.wg.Add(1)
	go b.accept()
	return b, nil
}

func (b *tcpBroker) Addr() string { return b.ln.Addr().String() }

func (b *tcpBroker) accept() {
	defer b.wg.Done()
	for {
		c, err := b.ln.Accept()
		if err != nil {
			select {
			case <-b.closed:
				return
			default:
				return
			}
		}
		cn := &conn{c: c, enc: json.NewEncoder(c)}
		b.mu.Lock()
		b.conns[cn] = struct{}{}
		b.mu.Unlock()
		b.wg.Add(1)
		go b.serve(cn)
	}
}

func (b *tcpBroker) serve(cn *conn) {
	defer b.wg.Done()
	defer func() {
		b.mu.Lock()
		delete(b.conns, cn)
		for _, set := range b.subs {
			delete(set, cn)
		}
		b.mu.Unlock()
		cn.c.Close()
	}()
	dec := json.NewDecoder(bufio.NewReaderSize(cn.c, 1<<16))
	for {
		var f frame
		if err := dec.Decode(&f); err != nil {
			if !errors.Is(err, io.EOF) {
				select {
				case <-b.closed:
				default:
				}
			}
			return
		}
		switch f.Kind {
		case "sub":
			b.mu.Lock()
			if b.subs[f.Subject] == nil {
				b.subs[f.Subject] = map[*conn]struct{}{}
			}
			b.subs[f.Subject][cn] = struct{}{}
			b.mu.Unlock()
		case "pub":
			b.mu.RLock()
			targets := make([]*conn, 0, len(b.subs[f.Subject]))
			for t := range b.subs[f.Subject] {
				targets = append(targets, t)
			}
			b.mu.RUnlock()
			// Fan-out order across subscribers is not fixed, and is not made
			// fixed: that variability is part of what D0 measures.
			for _, t := range targets {
				_ = t.send(frame{Kind: "pub", Subject: f.Subject, Env: f.Env})
			}
		}
	}
}

func (b *tcpBroker) Close() error {
	b.once.Do(func() {
		close(b.closed)
		b.ln.Close()
		b.mu.Lock()
		for c := range b.conns {
			c.c.Close()
		}
		b.mu.Unlock()
	})
	b.wg.Wait()
	return nil
}

// --- client -----------------------------------------------------------------

type tcpClient struct {
	c      net.Conn
	enc    *json.Encoder
	mu     sync.Mutex
	subs   map[string][]Handler
	submu  sync.RWMutex
	closed chan struct{}
	once   sync.Once
	desc   Descriptor
}

// DialTCP connects to a broker. Version is recorded in the descriptor so a
// manifest can name the exact transport that produced a measurement.
func DialTCP(addr string, timeout time.Duration) (Bus, error) {
	c, err := net.DialTimeout("tcp", addr, timeout)
	if err != nil {
		return nil, err
	}
	t := &tcpClient{
		c: c, enc: json.NewEncoder(c), subs: map[string][]Handler{},
		closed: make(chan struct{}),
		desc: Descriptor{
			Type: "stdlib-tcp", Version: "a1a-1",
			Config: map[string]string{"addr": addr, "framing": "json-lines"},
		},
	}
	go t.read()
	return t, nil
}

func (t *tcpClient) read() {
	dec := json.NewDecoder(bufio.NewReaderSize(t.c, 1<<16))
	for {
		var f frame
		if err := dec.Decode(&f); err != nil {
			return
		}
		t.submu.RLock()
		hs := append([]Handler(nil), t.subs[f.Subject]...)
		t.submu.RUnlock()
		for _, h := range hs {
			h(f.Env)
		}
	}
}

func (t *tcpClient) Publish(ctx context.Context, subject string, env Envelope) error {
	select {
	case <-t.closed:
		return fmt.Errorf("bus: closed")
	case <-ctx.Done():
		return ctx.Err()
	default:
	}
	env.Subject = subject
	t.mu.Lock()
	defer t.mu.Unlock()
	return t.enc.Encode(frame{Kind: "pub", Subject: subject, Env: env})
}

func (t *tcpClient) Subscribe(ctx context.Context, subject string, h Handler) error {
	t.submu.Lock()
	t.subs[subject] = append(t.subs[subject], h)
	t.submu.Unlock()
	t.mu.Lock()
	defer t.mu.Unlock()
	return t.enc.Encode(frame{Kind: "sub", Subject: subject})
}

func (t *tcpClient) Close() error {
	t.once.Do(func() { close(t.closed); t.c.Close() })
	return nil
}

func (t *tcpClient) Descriptor() Descriptor { return t.desc }
