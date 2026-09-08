//go:build !nats

// These two tests assert what the DEVELOPMENT build must NOT be able to do.
// Without this constraint they were compiled into the -tags=nats build as well,
// where they assert the opposite of that build's contract and fail by
// construction: `go test -tags=nats ./...` reported "nats must not be dialable"
// about a binary whose whole purpose is that nats is dialable.

package bus_test

import (
	"strings"
	"testing"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
)

func TestDefaultBuildOffersOnlyTCP(t *testing.T) {
	got := bus.Available()
	if len(got) != 1 || got[0] != "tcp" {
		t.Fatalf("without -tags=nats the binary must offer only tcp, got %v", got)
	}
}

// A misspelled or unavailable transport must fail loudly. Falling back to the
// development bus would attribute a measurement to the wrong stack, which is
// the one error this project cannot detect after the fact.
func TestUnknownTransportNamesTheBuildTag(t *testing.T) {
	_, err := bus.Dial("nats", "127.0.0.1:4222", time.Second)
	if err == nil {
		t.Fatal("nats must not be dialable in a build without the tag")
	}
	if !strings.Contains(err.Error(), "-tags=nats") {
		t.Fatalf("the error must name the build tag, got %q", err)
	}
}
