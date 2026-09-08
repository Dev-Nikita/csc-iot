//go:build nats

// The mirror image: what the reportable build must offer. A build tag that
// silently stopped taking effect would otherwise be invisible -- the negative
// tests would keep passing in the development build and nothing would assert
// that the NATS adapter is actually compiled in.

package bus_test

import (
	"slices"
	"strings"
	"testing"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
)

func TestNatsBuildOffersNats(t *testing.T) {
	got := bus.Available()
	if !slices.Contains(got, "nats") || !slices.Contains(got, "tcp") {
		t.Fatalf("the nats build must offer both transports, got %v", got)
	}
}

// An unavailable transport must still fail by name rather than fall back. The
// reason the negative case matters in this build too is that a fallback here
// would attribute a measurement to the wrong stack.
func TestUnknownTransportStillRefusedInNatsBuild(t *testing.T) {
	_, err := bus.Dial("kafka", "127.0.0.1:9092", time.Second)
	if err == nil {
		t.Fatal("an uncompiled transport must not be dialable")
	}
	if !strings.Contains(err.Error(), "kafka") {
		t.Fatalf("the error must name the transport asked for, got %q", err)
	}
}
