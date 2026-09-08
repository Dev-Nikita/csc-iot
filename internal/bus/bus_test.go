package bus_test

import (
	"context"
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
)

func startBus(t *testing.T) (string, func()) {
	t.Helper()
	b, err := bus.StartBroker("127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	return b.Addr(), func() { b.Close() }
}

func TestPublishSubscribeAcrossConnections(t *testing.T) {
	addr, stop := startBus(t)
	defer stop()
	ctx := context.Background()

	sub, err := bus.DialTCP(addr, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer sub.Close()

	got := make(chan bus.Envelope, 4)
	if err := sub.Subscribe(ctx, bus.SubjectEdgeWork, func(e bus.Envelope) { got <- e }); err != nil {
		t.Fatal(err)
	}
	time.Sleep(50 * time.Millisecond) // let the subscription register

	pub, err := bus.DialTCP(addr, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer pub.Close()
	if err := pub.Publish(ctx, bus.SubjectEdgeWork, bus.Envelope{
		ExperimentID: "x", LogicalTick: 7, ProducerID: "gw00", Seq: 1, EventID: "e1",
	}); err != nil {
		t.Fatal(err)
	}

	select {
	case e := <-got:
		if e.LogicalTick != 7 || e.ProducerID != "gw00" {
			t.Fatalf("envelope identity lost in transit: %+v", e)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("message never arrived")
	}
}

func TestSubjectIsolation(t *testing.T) {
	addr, stop := startBus(t)
	defer stop()
	ctx := context.Background()
	sub, _ := bus.DialTCP(addr, time.Second)
	defer sub.Close()
	other := make(chan bus.Envelope, 1)
	sub.Subscribe(ctx, bus.SubjectEdgeTelemetry, func(e bus.Envelope) { other <- e })
	time.Sleep(50 * time.Millisecond)

	pub, _ := bus.DialTCP(addr, time.Second)
	defer pub.Close()
	pub.Publish(ctx, bus.SubjectEdgeWork, bus.Envelope{EventID: "wrong-subject"})

	select {
	case e := <-other:
		t.Fatalf("subscriber received a message from another subject: %+v", e)
	case <-time.After(300 * time.Millisecond):
	}
}

// Per-producer ordering must hold: a gateway's own stream arriving out of order
// would make sequence positions useless for fingerprinting.
func TestPerProducerOrderPreserved(t *testing.T) {
	addr, stop := startBus(t)
	defer stop()
	ctx := context.Background()
	sub, _ := bus.DialTCP(addr, time.Second)
	defer sub.Close()
	const n = 200
	seen := make(chan uint64, n)
	sub.Subscribe(ctx, bus.SubjectEdgeWork, func(e bus.Envelope) { seen <- e.Seq })
	time.Sleep(50 * time.Millisecond)

	pub, _ := bus.DialTCP(addr, time.Second)
	defer pub.Close()
	for i := uint64(0); i < n; i++ {
		if err := pub.Publish(ctx, bus.SubjectEdgeWork, bus.Envelope{ProducerID: "gw00", Seq: i}); err != nil {
			t.Fatal(err)
		}
	}
	for i := uint64(0); i < n; i++ {
		select {
		case got := <-seen:
			if got != i {
				t.Fatalf("out-of-order delivery from one producer: expected %d got %d", i, got)
			}
		case <-time.After(3 * time.Second):
			t.Fatalf("only %d of %d messages arrived", i, n)
		}
	}
}

func TestConcurrentPublishersDoNotCorruptFrames(t *testing.T) {
	addr, stop := startBus(t)
	defer stop()
	ctx := context.Background()
	sub, _ := bus.DialTCP(addr, time.Second)
	defer sub.Close()
	const producers, each = 8, 50
	seen := make(chan bus.Envelope, producers*each)
	sub.Subscribe(ctx, bus.SubjectEdgeWork, func(e bus.Envelope) { seen <- e })
	time.Sleep(50 * time.Millisecond)

	pub, _ := bus.DialTCP(addr, time.Second)
	defer pub.Close()
	var wg sync.WaitGroup
	for p := 0; p < producers; p++ {
		wg.Add(1)
		go func(p int) {
			defer wg.Done()
			for i := 0; i < each; i++ {
				pub.Publish(ctx, bus.SubjectEdgeWork, bus.Envelope{
					ProducerID: fmt.Sprintf("p%02d", p), Seq: uint64(i),
				})
			}
		}(p)
	}
	wg.Wait()

	counts := map[string]int{}
	deadline := time.After(4 * time.Second)
	for i := 0; i < producers*each; i++ {
		select {
		case e := <-seen:
			counts[e.ProducerID]++
		case <-deadline:
			t.Fatalf("received only %d of %d", i, producers*each)
		}
	}
	for p := 0; p < producers; p++ {
		id := fmt.Sprintf("p%02d", p)
		if counts[id] != each {
			t.Fatalf("producer %s: %d messages, want %d", id, counts[id], each)
		}
	}
}

func TestDescriptorNamesTheTransportHonestly(t *testing.T) {
	addr, stop := startBus(t)
	defer stop()
	c, _ := bus.DialTCP(addr, time.Second)
	defer c.Close()
	d := c.Descriptor()
	if d.Type != "stdlib-tcp" {
		t.Fatalf("descriptor must name the real transport, got %q", d.Type)
	}
	if d.Type == "nats" {
		t.Fatal("the stdlib broker must never describe itself as NATS")
	}
	if d.ConfigHash() == "" {
		t.Fatal("transport config hash missing; eta_J could not be attributed to a stack")
	}
}
