package epoch_test

import (
	"context"
	"testing"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
	"github.com/TODO-OWNER/csc-iot/internal/epoch"
)

// Every test speaks for one run; run identity is what keeps a previous
// invocation's confirmations from answering this one.
const testRun = "test-run"

func wm(t *testing.T, addr string, consumers []string) (*epoch.Watermark, func()) {
	t.Helper()
	b, err := bus.DialTCP(addr, time.Second)
	if err != nil {
		t.Fatal(err)
	}
	w, err := epoch.NewWatermark(context.Background(), b, testRun, consumers)
	if err != nil {
		t.Fatal(err)
	}
	time.Sleep(60 * time.Millisecond)
	return w, func() { b.Close() }
}

// The defect the protocol exists to prevent: a producer finished locally, but a
// message it sent is still in flight. Local ACKs alone would open the anchor.
func TestUndrainedTransportBlocksTheAnchor(t *testing.T) {
	addr, stop := setup(t)
	defer stop()
	ctx := context.Background()
	w, closeW := wm(t, addr, []string{"edge00"})
	defer closeW()

	pw, _ := bus.DialTCP(addr, time.Second)
	defer pw.Close()
	pwm, _ := epoch.NewWatermark(ctx, pw, testRun, []string{"edge00"})
	if err := pwm.DeclareEnd(ctx, 5, "gw00", bus.SubjectEdgeWork, 100); err != nil {
		t.Fatal(err)
	}
	// The consumer has only got as far as 97: three messages are still in flight.
	if err := pwm.ConfirmDrained(ctx, 5, "edge00", "gw00", bus.SubjectEdgeWork, 97); err != nil {
		t.Fatal(err)
	}

	err := w.AwaitQuiescent(ctx, 5, 500*time.Millisecond)
	if err == nil {
		t.Fatal("anchor opened while three messages were still in flight")
	}
	if !contains(err.Error(), "97 of 100") {
		t.Fatalf("the error must say how far behind the consumer is, got %q", err)
	}

	// Once the consumer catches up, the anchor may open.
	if err := pwm.ConfirmDrained(ctx, 5, "edge00", "gw00", bus.SubjectEdgeWork, 100); err != nil {
		t.Fatal(err)
	}
	if err := w.AwaitQuiescent(ctx, 5, 2*time.Second); err != nil {
		t.Fatalf("anchor did not open after the transport drained: %v", err)
	}
}

func TestEveryConsumerMustConfirmEveryProducer(t *testing.T) {
	addr, stop := setup(t)
	defer stop()
	ctx := context.Background()
	w, closeW := wm(t, addr, []string{"edge00", "edge01"})
	defer closeW()

	pw, _ := bus.DialTCP(addr, time.Second)
	defer pw.Close()
	pwm, _ := epoch.NewWatermark(ctx, pw, testRun, []string{"edge00", "edge01"})
	for _, p := range []string{"gw00", "gw01"} {
		pwm.DeclareEnd(ctx, 3, p, bus.SubjectEdgeWork, 10)
	}
	// edge01 never confirms gw01.
	pwm.ConfirmDrained(ctx, 3, "edge00", "gw00", bus.SubjectEdgeWork, 10)
	pwm.ConfirmDrained(ctx, 3, "edge00", "gw01", bus.SubjectEdgeWork, 10)
	pwm.ConfirmDrained(ctx, 3, "edge01", "gw00", bus.SubjectEdgeWork, 10)

	err := w.AwaitQuiescent(ctx, 3, 400*time.Millisecond)
	if err == nil {
		t.Fatal("anchor opened with an unconfirmed producer/consumer pair")
	}
	if !contains(err.Error(), "edge01 has not confirmed gw01") {
		t.Fatalf("the error must name the missing pair, got %q", err)
	}
}

func TestQuiescenceFingerprintDistinguishesDrainState(t *testing.T) {
	addr, stop := setup(t)
	defer stop()
	ctx := context.Background()
	w, closeW := wm(t, addr, []string{"edge00"})
	defer closeW()
	pw, _ := bus.DialTCP(addr, time.Second)
	defer pw.Close()
	pwm, _ := epoch.NewWatermark(ctx, pw, testRun, []string{"edge00"})

	pwm.DeclareEnd(ctx, 9, "gw00", bus.SubjectEdgeWork, 50)
	pwm.ConfirmDrained(ctx, 9, "edge00", "gw00", bus.SubjectEdgeWork, 50)
	if err := w.AwaitQuiescent(ctx, 9, 2*time.Second); err != nil {
		t.Fatal(err)
	}
	fp, err := w.TransportQuiescenceFingerprintVerified(9)
	if err != nil {
		t.Fatal(err)
	}
	if fp["end:gw00"] != 50 || fp["drained:edge00:gw00"] != 50 {
		t.Fatalf("fingerprint lost the watermark: %v", fp)
	}
	if len(fp) != 2 {
		t.Fatalf("fingerprint should carry one entry per declaration and confirmation, got %v", fp)
	}
}

func TestNoProducerDeclarationIsNotQuiescent(t *testing.T) {
	addr, stop := setup(t)
	defer stop()
	w, closeW := wm(t, addr, []string{"edge00"})
	defer closeW()
	// An epoch nobody declared must not be treated as trivially drained --
	// "nothing was declared" and "everything was consumed" are not the same.
	if err := w.AwaitQuiescent(context.Background(), 42, 300*time.Millisecond); err == nil {
		t.Fatal("an epoch with no end-of-epoch declaration was reported quiescent")
	}
}

// The defect that produced the quarantined anchor: a saved fingerprint recording
// drained:edge00:gw00 = 1866 against end:gw00 = 2000, accepted because the check
// and the snapshot were two different moments and a stale confirmation had moved
// the watermark backwards in between.
func TestAcceptedSnapshotNeverRecordsDrainBelowDeclaredEnd(t *testing.T) {
	addr, stop := setup(t)
	defer stop()
	ctx := context.Background()
	w, closeW := wm(t, addr, []string{"edge00"})
	defer closeW()
	pw, _ := bus.DialTCP(addr, time.Second)
	defer pw.Close()
	pwm, _ := epoch.NewWatermark(ctx, pw, testRun, []string{"edge00"})

	pwm.DeclareEnd(ctx, 7, "gw00", bus.SubjectEdgeWork, 2000)
	pwm.ConfirmDrained(ctx, 7, "edge00", "gw00", bus.SubjectEdgeWork, 2000)
	if err := w.AwaitQuiescent(ctx, 7, 2*time.Second); err != nil {
		t.Fatal(err)
	}

	// A late duplicate of an earlier confirmation arrives after the check.
	// Before the watermark was monotonic this overwrote 2000 with 1866 and the
	// anchor was written anyway.
	pwm.ConfirmDrained(ctx, 7, "edge00", "gw00", bus.SubjectEdgeWork, 1866)
	time.Sleep(150 * time.Millisecond)

	fp, err := w.TransportQuiescenceFingerprintVerified(7)
	if err != nil {
		t.Fatalf("a stale confirmation must not unmake quiescence: %v", err)
	}
	if fp["drained:edge00:gw00"] != 2000 {
		t.Fatalf("watermark regressed to %d", fp["drained:edge00:gw00"])
	}

	// And the invariant itself, stated over the snapshot that would be written.
	for consumerProducer, got := range fp {
		if !contains(consumerProducer, "drained:") {
			continue
		}
		if got < fp["end:gw00"] {
			t.Fatalf("anchor would record %s = %d below end 2000", consumerProducer, got)
		}
	}
}

// A confirmation from another run must not be counted towards this one. Epoch
// numbers restart at 1 on every invocation while the nodes keep running.
func TestConfirmationsFromAnotherRunDoNotOpenTheAnchor(t *testing.T) {
	addr, stop := setup(t)
	defer stop()
	ctx := context.Background()
	w, closeW := wm(t, addr, []string{"edge00"})
	defer closeW()

	other, _ := bus.DialTCP(addr, time.Second)
	defer other.Close()
	owm, _ := epoch.NewWatermark(ctx, other, "a-previous-run", []string{"edge00"})
	owm.DeclareEnd(ctx, 3, "gw00", bus.SubjectEdgeWork, 100)
	owm.ConfirmDrained(ctx, 3, "edge00", "gw00", bus.SubjectEdgeWork, 100)
	time.Sleep(150 * time.Millisecond)

	if err := w.AwaitQuiescent(ctx, 3, 300*time.Millisecond); err == nil {
		t.Fatal("epoch 3 of a previous run opened the anchor for epoch 3 of this one")
	}
}

// Quiescence must not be transiently true. With only one of two producers
// declared, "everything declared has been drained" is satisfied while the other
// producer is still working -- and a fingerprint read in that window records a
// state nobody had finished producing.
func TestEpochIsNotQuiescentUntilEveryProducerHasDeclared(t *testing.T) {
	addr, stop := setup(t)
	defer stop()
	ctx := context.Background()
	w, closeW := wm(t, addr, []string{"edge00", "edge01"})
	defer closeW()
	w.ExpectProducers([]string{"gw00", "gw01"})

	pw, _ := bus.DialTCP(addr, time.Second)
	defer pw.Close()
	pwm, _ := epoch.NewWatermark(ctx, pw, testRun, []string{"edge00", "edge01"})

	// The idle gateway closes the epoch immediately and its consumer confirms.
	pwm.DeclareEnd(ctx, 3, "gw01", bus.EdgeWorkSubject("edge01"), 0)
	pwm.ConfirmDrained(ctx, 3, "edge01", "gw01", bus.EdgeWorkSubject("edge01"), 0)
	time.Sleep(150 * time.Millisecond)

	if _, err := w.TransportQuiescenceFingerprintVerified(3); err == nil {
		t.Fatal("the epoch was read while gw00 had not declared an end")
	}
	if err := w.AwaitQuiescent(ctx, 3, 300*time.Millisecond); err == nil {
		t.Fatal("AwaitQuiescent returned before gw00 declared")
	}

	pwm.DeclareEnd(ctx, 3, "gw00", bus.EdgeWorkSubject("edge00"), 40)
	pwm.ConfirmDrained(ctx, 3, "edge00", "gw00", bus.EdgeWorkSubject("edge00"), 40)
	if err := w.AwaitQuiescent(ctx, 3, 2*time.Second); err != nil {
		t.Fatalf("epoch stayed closed after both producers finished: %v", err)
	}
}
