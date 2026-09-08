package bus_test

import (
	"testing"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
)

func TestTCPStillDialable(t *testing.T) {
	b, err := bus.StartBroker("127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close()
	c, err := bus.Dial("tcp", b.Addr(), time.Second)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	if c.Descriptor().Type != "stdlib-tcp" {
		t.Fatalf("descriptor must name the real transport, got %q", c.Descriptor().Type)
	}
}
