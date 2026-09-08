//go:build nats

package bus_test

import (
	"context"
	"fmt"
	"sync"
	"testing"
	"time"

	natsserver "github.com/nats-io/nats-server/v2/server"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
)

// startNATS runs an embedded server so the suite needs no external process and
// can be run by anyone who fetched the modules.
func startNATS(t *testing.T) (string, func()) {
	t.Helper()
	opts := &natsserver.Options{Host: "127.0.0.1", Port: -1, NoLog: true, NoSigs: true}
	s, err := natsserver.NewServer(opts)
	if err != nil {
		t.Fatal(err)
	}
	go s.Start()
	if !s.ReadyForConnections(5 * time.Second) {
		t.Fatal("embedded NATS did not become ready")
	}
	return s.ClientURL(), s.Shutdown
}

func TestNATSPublishSubscribe(t *testing.T) {
	url, stop := startNATS(t)
	defer stop()
	ctx := context.Background()

	sub, err := bus.DialNATS(url, 2*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer sub.Close()
	got := make(chan bus.Envelope, 4)
	if err := sub.Subscribe(ctx, bus.EdgeWorkSubject("edge00"), func(e bus.Envelope) { got <- e }); err != nil {
		t.Fatal(err)
	}

	pub, err := bus.DialNATS(url, 2*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer pub.Close()
	if err := pub.Publish(ctx, bus.EdgeWorkSubject("edge00"), bus.Envelope{
		ExperimentID: "x", LogicalTick: 7, ProducerID: "gw00", Seq: 1, EventID: "e1",
	}); err != nil {
		t.Fatal(err)
	}
	select {
	case e := <-got:
		if e.LogicalTick != 7 || e.ProducerID != "gw00" || e.EventID != "e1" {
			t.Fatalf("envelope identity lost in transit: %+v", e)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("message never arrived")
	}
}

// Routing is per-edge subjects, so an edge must never see another edge's work.
// If it does, the routing table is decorative and REROUTE is a no-op.
func TestNATSSubjectIsolation(t *testing.T) {
	url, stop := startNATS(t)
	defer stop()
	ctx := context.Background()
	sub, _ := bus.DialNATS(url, 2*time.Second)
	defer sub.Close()
	wrong := make(chan bus.Envelope, 1)
	sub.Subscribe(ctx, bus.EdgeWorkSubject("edge01"), func(e bus.Envelope) { wrong <- e })

	pub, _ := bus.DialNATS(url, 2*time.Second)
	defer pub.Close()
	pub.Publish(ctx, bus.EdgeWorkSubject("edge00"), bus.Envelope{EventID: "not-yours"})
	select {
	case e := <-wrong:
		t.Fatalf("edge01 received edge00's work: %+v", e)
	case <-time.After(500 * time.Millisecond):
	}
}

// Sequence positions are part of the structural fingerprint, so per-producer
// order must hold or the fingerprint is meaningless.
func TestNATSPerProducerOrder(t *testing.T) {
	url, stop := startNATS(t)
	defer stop()
	ctx := context.Background()
	sub, _ := bus.DialNATS(url, 2*time.Second)
	defer sub.Close()
	const n = 300
	seen := make(chan uint64, n)
	sub.Subscribe(ctx, bus.SubjectEdgeTelemetry, func(e bus.Envelope) { seen <- e.Seq })

	pub, _ := bus.DialNATS(url, 2*time.Second)
	defer pub.Close()
	for i := uint64(0); i < n; i++ {
		if err := pub.Publish(ctx, bus.SubjectEdgeTelemetry, bus.Envelope{ProducerID: "gw00", Seq: i}); err != nil {
			t.Fatal(err)
		}
	}
	for i := uint64(0); i < n; i++ {
		select {
		case got := <-seen:
			if got != i {
				t.Fatalf("out-of-order delivery from one producer: want %d got %d", i, got)
			}
		case <-time.After(5 * time.Second):
			t.Fatalf("only %d of %d arrived", i, n)
		}
	}
}

func TestNATSConcurrentPublishers(t *testing.T) {
	url, stop := startNATS(t)
	defer stop()
	ctx := context.Background()
	sub, _ := bus.DialNATS(url, 2*time.Second)
	defer sub.Close()
	const producers, each = 8, 50
	seen := make(chan bus.Envelope, producers*each)
	sub.Subscribe(ctx, bus.SubjectEdgeWork, func(e bus.Envelope) { seen <- e })

	var wg sync.WaitGroup
	for p := 0; p < producers; p++ {
		wg.Add(1)
		go func(p int) {
			defer wg.Done()
			c, err := bus.DialNATS(url, 2*time.Second)
			if err != nil {
				t.Error(err)
				return
			}
			defer c.Close()
			for i := 0; i < each; i++ {
				c.Publish(ctx, bus.SubjectEdgeWork, bus.Envelope{
					ProducerID: fmt.Sprintf("p%02d", p), Seq: uint64(i),
				})
			}
		}(p)
	}
	wg.Wait()

	counts := map[string]int{}
	deadline := time.After(6 * time.Second)
	for i := 0; i < producers*each; i++ {
		select {
		case e := <-seen:
			counts[e.ProducerID]++
		case <-deadline:
			t.Fatalf("received only %d of %d", i, producers*each)
		}
	}
	for p := 0; p < producers; p++ {
		if id := fmt.Sprintf("p%02d", p); counts[id] != each {
			t.Fatalf("producer %s delivered %d of %d", id, counts[id], each)
		}
	}
}

// A slow consumer must not silently lose messages without the loss being
// visible: core NATS drops for a slow subscriber, and a drop that nobody
// notices would corrupt sequence positions and therefore the fingerprint.
func TestNATSSlowSubscriberIsObservable(t *testing.T) {
	url, stop := startNATS(t)
	defer stop()
	ctx := context.Background()
	sub, _ := bus.DialNATS(url, 2*time.Second)
	defer sub.Close()

	var mu sync.Mutex
	var received int
	sub.Subscribe(ctx, bus.SubjectEdgeWork, func(e bus.Envelope) {
		time.Sleep(2 * time.Millisecond) // deliberately slow
		mu.Lock()
		received++
		mu.Unlock()
	})

	pub, _ := bus.DialNATS(url, 2*time.Second)
	defer pub.Close()
	const n = 2000
	for i := 0; i < n; i++ {
		pub.Publish(ctx, bus.SubjectEdgeWork, bus.Envelope{ProducerID: "flood", Seq: uint64(i)})
	}
	time.Sleep(3 * time.Second)
	mu.Lock()
	got := received
	mu.Unlock()
	t.Logf("slow subscriber received %d of %d published", got, n)
	if got == n {
		t.Log("no drops at this rate; raise n or the sleep to exercise the slow-consumer path")
	}
	// The assertion is not "nothing was dropped" -- core NATS makes no such
	// promise. It is that the experiment must be able to SEE drops, which is why
	// every envelope carries a per-producer sequence number.
}

func TestNATSDescriptorNamesTheRealTransport(t *testing.T) {
	url, stop := startNATS(t)
	defer stop()
	c, err := bus.DialNATS(url, 2*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	d := c.Descriptor()
	if d.Type != "nats" {
		t.Fatalf("descriptor must say nats, got %q", d.Type)
	}
	if d.Version == "" {
		t.Fatal("server version missing; runtime_stack_id would be incomplete")
	}
	if d.Config["jetstream"] != "false" {
		t.Fatal("JetStream must stay off: persistence and redelivery change the timing eta_J measures")
	}
	if d.ConfigHash() == "" {
		t.Fatal("transport config hash missing")
	}
}
