package fingerprint_test

// One stack, one identity. There were two implementations of it: this package's
// RuntimeStack.ID and cmd/csc-stackstamp's own, and they disagreed in two
// places. The stamper now calls this package, and these assertions are what
// keeps a second copy from reappearing.

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"testing"

	"github.com/TODO-OWNER/csc-iot/internal/fingerprint"
)

func stampSerialisation(r fingerprint.RuntimeStack) string {
	h := sha256.New()
	fmt.Fprintf(h, "%s|%s|%s|%s|%s|%s|%s|%s|",
		r.GoVersion, r.Kernel, r.BusType, r.BusVersion,
		r.TransportHash, r.RPCType, r.ProcessTopology,
		fingerprint.StableNetemConfig(r.NetemConfig))
	keys := make([]string, 0, len(r.Images))
	for k := range r.Images {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		fmt.Fprintf(h, "%s=%s;", k, r.Images[k])
	}
	return hex.EncodeToString(h.Sum(nil))[:16]
}

func sample() fingerprint.RuntimeStack {
	return fingerprint.RuntimeStack{
		GoVersion: "go1.26.10 linux/amd64", Kernel: "Linux 7.0.0-38-generic",
		BusType: "nats", BusVersion: "nats-server: v2.15.2",
		TransportHash: "6449b1c90d4c4527", RPCType: "stdlib-framed-tcp",
		ProcessTopology: "1 broker, 2 gateways, 3 edges",
		NetemConfig:     "device-sim:eth0 qdisc netem 8e48: root refcnt 5 limit 1000 delay 20ms  5ms loss 5% seed 424242",
		Images:          map[string]string{"gateway00": "a@sha256:1", "nats": "b@sha256:2"},
	}
}

func TestRuntimeStackIDMatchesStampSerialisation(t *testing.T) {
	r := sample()
	if got, want := r.ID(), stampSerialisation(r); got != want {
		t.Fatalf("two serialisations of one stack disagree: %s vs %s", got, want)
	}
}

func TestRecreatingTheTopologyKeepsTheIdentity(t *testing.T) {
	a := sample()
	b := sample()
	// Linux reassigns the qdisc handle and the refcnt on every recreation.
	b.NetemConfig = "device-sim:eth0 qdisc netem 1f3a: root refcnt 2 limit 1000 delay 20ms  5ms loss 5% seed 424242"
	if a.ID() != b.ID() {
		t.Fatalf("a recreated identical topology got a new stack id: %s vs %s",
			a.ID(), b.ID())
	}
}

func TestRealImpairmentChangeDoesChangeTheIdentity(t *testing.T) {
	a := sample()
	b := sample()
	b.NetemConfig = "device-sim:eth0 qdisc netem 8e48: root refcnt 5 limit 1000 delay 40ms  5ms loss 5% seed 424242"
	if a.ID() == b.ID() {
		t.Fatal("changing the delay left the stack id unchanged")
	}
}
