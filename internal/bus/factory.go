package bus

import (
	"fmt"
	"sort"
	"sync"
	"time"
)

// Dialer constructs a Bus for one transport implementation.
type Dialer func(addr string, timeout time.Duration) (Bus, error)

var (
	regMu sync.RWMutex
	reg   = map[string]Dialer{}
)

// Register makes a transport available to Dial. Tagged adapters call this from
// init(), so a binary built without the tag simply does not offer that
// transport rather than failing to compile.
func Register(kind string, d Dialer) {
	regMu.Lock()
	defer regMu.Unlock()
	reg[kind] = d
}

func init() { Register("tcp", DialTCP) }

// Available lists the transports compiled into this binary.
func Available() []string {
	regMu.RLock()
	defer regMu.RUnlock()
	out := make([]string, 0, len(reg))
	for k := range reg {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

// Dial opens the named transport.
//
// The error when a transport is absent names the build tag rather than saying
// "unknown". A binary silently running on the development transport because the
// operator misspelled a flag is exactly how a measurement gets attributed to
// the wrong stack.
func Dial(kind, addr string, timeout time.Duration) (Bus, error) {
	regMu.RLock()
	d, ok := reg[kind]
	regMu.RUnlock()
	if !ok {
		return nil, fmt.Errorf(
			"bus: transport %q is not compiled into this binary (available: %v); "+
				"the NATS adapter requires -tags=nats", kind, Available())
	}
	return d(addr, timeout)
}
