package epoch_test

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
	"github.com/TODO-OWNER/csc-iot/internal/epoch"
)

func setup(t *testing.T) (string, func()) {
	t.Helper()
	b, err := bus.StartBroker("127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	return b.Addr(), func() { b.Close() }
}

func TestBarrierWaitsForEveryParticipant(t *testing.T) {
	addr, stop := setup(t)
	defer stop()
	ctx := context.Background()
	names := []string{"gw00", "gw01", "edge00", "edge01"}

	cbus, _ := bus.DialTCP(addr, time.Second)
	defer cbus.Close()
	coord, err := epoch.NewCoordinator(ctx, cbus, "test-run", names)
	if err != nil {
		t.Fatal(err)
	}

	var done int64
	var wg sync.WaitGroup
	for _, n := range names {
		pb, _ := bus.DialTCP(addr, time.Second)
		defer pb.Close()
		wg.Add(1)
		if _, err := epoch.NewParticipant(ctx, pb, n, func(_ string, k int64) {
			// Different components take different amounts of time; the barrier
			// exists precisely because they do.
			time.Sleep(time.Duration(len(n)) * 10 * time.Millisecond)
			atomic.AddInt64(&done, 1)
		}); err != nil {
			t.Fatal(err)
		}
		wg.Done()
	}
	wg.Wait()
	time.Sleep(100 * time.Millisecond)

	if err := coord.Declare(ctx, 7); err != nil {
		t.Fatal(err)
	}
	if err := coord.Await(ctx, 7, 3*time.Second); err != nil {
		t.Fatalf("barrier did not close: %v", err)
	}
	if got := atomic.LoadInt64(&done); got != int64(len(names)) {
		t.Fatalf("barrier released with %d/%d participants finished", got, len(names))
	}
}

// A barrier that proceeds with a participant missing would produce branches
// whose prefixes were never equal. It must fail loudly instead.
func TestBarrierTimesOutAndNamesTheMissing(t *testing.T) {
	addr, stop := setup(t)
	defer stop()
	ctx := context.Background()

	cbus, _ := bus.DialTCP(addr, time.Second)
	defer cbus.Close()
	coord, _ := epoch.NewCoordinator(ctx, cbus, "test-run", []string{"present", "absent"})

	pb, _ := bus.DialTCP(addr, time.Second)
	defer pb.Close()
	epoch.NewParticipant(ctx, pb, "present", nil)
	time.Sleep(100 * time.Millisecond)

	coord.Declare(ctx, 1)
	err := coord.Await(ctx, 1, 400*time.Millisecond)
	if err == nil {
		t.Fatal("barrier closed without every participant")
	}
	if !contains(err.Error(), "absent") {
		t.Fatalf("timeout must name who was missing, got %q", err)
	}
}

func TestSequentialEpochs(t *testing.T) {
	addr, stop := setup(t)
	defer stop()
	ctx := context.Background()
	names := []string{"a", "b", "c"}
	cbus, _ := bus.DialTCP(addr, time.Second)
	defer cbus.Close()
	coord, _ := epoch.NewCoordinator(ctx, cbus, "test-run", names)
	var order sync.Map
	for _, n := range names {
		pb, _ := bus.DialTCP(addr, time.Second)
		defer pb.Close()
		name := n
		epoch.NewParticipant(ctx, pb, name, func(_ string, k int64) {
			order.Store(fmt.Sprintf("%s-%d", name, k), true)
		})
	}
	time.Sleep(100 * time.Millisecond)
	for k := int64(1); k <= 5; k++ {
		if err := coord.Declare(ctx, k); err != nil {
			t.Fatal(err)
		}
		if err := coord.Await(ctx, k, 2*time.Second); err != nil {
			t.Fatalf("epoch %d: %v", k, err)
		}
		for _, n := range names {
			if _, ok := order.Load(fmt.Sprintf("%s-%d", n, k)); !ok {
				t.Fatalf("%s did not process epoch %d before the barrier closed", n, k)
			}
		}
	}
}

func contains(s, sub string) bool {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
