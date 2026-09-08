// Package routing holds the gateway-to-edge routing table and the source rate
// limiters -- the two pieces of state that recovery actions actually mutate.
//
// This matters more than it looks. An action that subtracts a constant from a
// latency variable is a simulation wearing a system's clothes. REROUTE here
// changes which edge a gateway forwards to, and every downstream consequence
// (queue growth at the new edge, relief at the old one) follows from the
// system's own dynamics rather than from an assumed effect size.
package routing

import (
	"fmt"
	"sort"
	"sync"
)

type Table struct {
	mu sync.RWMutex
	// gateway id -> edge id
	route map[string]string
	// gateway id -> multiplier in [0,1] applied to admitted source rate
	throttle map[string]float64
	edges    []string
}

func NewTable(gateways, edges []string) *Table {
	t := &Table{route: map[string]string{}, throttle: map[string]float64{}, edges: append([]string(nil), edges...)}
	for i, g := range gateways {
		t.route[g] = edges[i%len(edges)]
		t.throttle[g] = 1.0
	}
	return t
}

func (t *Table) EdgeFor(gw string) string {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return t.route[gw]
}

func (t *Table) ThrottleFor(gw string) float64 {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return t.throttle[gw]
}

// Reroute moves a gateway to the given edge. Returns the previous edge so the
// controller can log what actually changed rather than what it intended.
func (t *Table) Reroute(gw, edge string) (string, error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if _, ok := t.route[gw]; !ok {
		return "", fmt.Errorf("unknown gateway %q", gw)
	}
	found := false
	for _, e := range t.edges {
		if e == edge {
			found = true
			break
		}
	}
	if !found {
		return "", fmt.Errorf("unknown edge %q", edge)
	}
	prev := t.route[gw]
	t.route[gw] = edge
	return prev, nil
}

// Throttle sets the admitted fraction of the source rate for a gateway.
func (t *Table) Throttle(gw string, factor float64) (float64, error) {
	if factor <= 0 || factor > 1 {
		return 0, fmt.Errorf("throttle factor must be in (0,1], got %v", factor)
	}
	t.mu.Lock()
	defer t.mu.Unlock()
	if _, ok := t.throttle[gw]; !ok {
		return 0, fmt.Errorf("unknown gateway %q", gw)
	}
	prev := t.throttle[gw]
	t.throttle[gw] = factor
	return prev, nil
}

// Snapshot returns a stable, sorted view for telemetry and replay hashing.
func (t *Table) Snapshot() (routes map[string]string, throttles map[string]float64) {
	t.mu.RLock()
	defer t.mu.RUnlock()
	routes, throttles = map[string]string{}, map[string]float64{}
	keys := make([]string, 0, len(t.route))
	for k := range t.route {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		routes[k] = t.route[k]
		throttles[k] = t.throttle[k]
	}
	return
}
