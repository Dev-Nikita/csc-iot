package rpc

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"net"
	"sync"
	"time"
)

// framedClient is the development RPC implementation: length-agnostic JSON
// lines over stdlib TCP. It is not gRPC and its descriptor says so.
type framedClient struct {
	mu   sync.Mutex
	conn net.Conn
	enc  *json.Encoder
	dec  *json.Decoder
	desc Descriptor
}

func DialFramed(addr string, timeout time.Duration) (Client, error) {
	c, err := net.DialTimeout("tcp", addr, timeout)
	if err != nil {
		return nil, err
	}
	return &framedClient{
		conn: c,
		enc:  json.NewEncoder(c),
		dec:  json.NewDecoder(bufio.NewReaderSize(c, 1<<16)),
		desc: Descriptor{Type: "stdlib-framed-tcp", Version: "a1a-1", Address: addr},
	}, nil
}

func (f *framedClient) EvaluateActions(ctx context.Context, req StateRequest) (ActionScores, Timing, error) {
	deadline, ok := ctx.Deadline()
	if !ok {
		deadline = time.Now().Add(Deadline)
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	_ = f.conn.SetDeadline(deadline)

	start := time.Now()
	if err := f.enc.Encode(req); err != nil {
		return ActionScores{}, Timing{RPCNanos: time.Since(start).Nanoseconds(), DeadlineMissed: true}, err
	}
	var resp ActionScores
	if err := f.dec.Decode(&resp); err != nil {
		// A timeout here is a fallback, recorded as such. The controller must
		// keep control of the system rather than wait on the model.
		return ActionScores{}, Timing{
			RPCNanos:       time.Since(start).Nanoseconds(),
			DeadlineMissed: true,
		}, fmt.Errorf("rpc: %w", err)
	}
	rpcNanos := time.Since(start).Nanoseconds()
	return resp, Timing{
		RPCNanos:            rpcNanos - resp.TModelNanos - resp.TCounterfactualNanos,
		ModelNanos:          resp.TModelNanos,
		CounterfactualNanos: resp.TCounterfactualNanos,
	}, nil
}

func (f *framedClient) Descriptor() Descriptor { return f.desc }

func (f *framedClient) Close() error { return f.conn.Close() }

// StubServer answers with deterministic scores. Before a model exists its
// purpose is not to be right but to make the boundary measurable: latency, the
// deadline, and the fallback path.
type StubServer struct {
	ln    net.Listener
	delay time.Duration
	wg    sync.WaitGroup
	once  sync.Once
	done  chan struct{}
}

func StartStub(addr string, delay time.Duration) (*StubServer, error) {
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		return nil, err
	}
	s := &StubServer{ln: ln, delay: delay, done: make(chan struct{})}
	s.wg.Add(1)
	go s.accept()
	return s, nil
}

func (s *StubServer) Addr() string { return s.ln.Addr().String() }

func (s *StubServer) accept() {
	defer s.wg.Done()
	for {
		c, err := s.ln.Accept()
		if err != nil {
			return
		}
		s.wg.Add(1)
		go s.serve(c)
	}
}

func (s *StubServer) serve(c net.Conn) {
	defer s.wg.Done()
	defer c.Close()
	dec := json.NewDecoder(bufio.NewReaderSize(c, 1<<16))
	enc := json.NewEncoder(c)
	for {
		var req StateRequest
		if err := dec.Decode(&req); err != nil {
			return
		}
		select {
		case <-time.After(s.delay):
		case <-s.done:
			return
		}
		scores := make([]ActionScore, 0, len(req.Actions))
		for i, a := range req.Actions {
			// Deterministic and obviously synthetic: a stub that looked like a
			// plausible model would invite someone to read meaning into it.
			v := float64(i+1) / float64(len(req.Actions)+1)
			scores = append(scores, ActionScore{
				Action: a, RiskObservational: v, RiskInterventional: v,
				Uncertainty: 0.1, Cost: v / 2,
			})
		}
		_ = enc.Encode(ActionScores{
			DecisionID: req.DecisionID, Scores: scores,
			ModelVersion: "stub", CalibrationVersion: "stub",
			TModelNanos: int64(s.delay), TCounterfactualNanos: 0,
		})
	}
}

func (s *StubServer) Close() error {
	s.once.Do(func() { close(s.done); s.ln.Close() })
	s.wg.Wait()
	return nil
}
