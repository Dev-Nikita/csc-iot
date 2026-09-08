// Package rng derives independent random streams from one master seed.
//
// A single global stream is forbidden. If mobility and fault scheduling drew
// from the same generator, adding one draw in mobility would reshuffle the
// fault schedule, and reproducibility would break on an innocent refactor --
// the failure mode is silent, and it invalidates every replay taken before it.
package rng

import (
	"crypto/sha256"
	"encoding/binary"
	"math/rand"
)

// Component names the independent streams. Adding a component must not
// perturb the others, which is exactly what hash-derived seeding gives.
type Component string

const (
	Workload   Component = "workload"
	Mobility   Component = "mobility"
	Network    Component = "network"
	Service    Component = "service"
	Fault      Component = "fault"
	Controller Component = "controller"
	Behaviour  Component = "behaviour"
)

// All returns every component, for validation and manifest recording.
func All() []Component {
	return []Component{Workload, Mobility, Network, Service, Fault, Controller, Behaviour}
}

// Derive computes seed_i = SHA256(master || component || instance).
// instance separates per-device or per-node streams inside one component so
// that adding the 101st device does not change what the first 100 do.
func Derive(master uint64, c Component, instance uint64) int64 {
	var buf [8]byte
	h := sha256.New()
	binary.BigEndian.PutUint64(buf[:], master)
	h.Write(buf[:])
	h.Write([]byte(c))
	binary.BigEndian.PutUint64(buf[:], instance)
	h.Write(buf[:])
	sum := h.Sum(nil)
	return int64(binary.BigEndian.Uint64(sum[:8]) >> 1) // keep it non-negative
}

// Streams hands out per-component generators from one master seed.
type Streams struct{ master uint64 }

func New(master uint64) *Streams { return &Streams{master: master} }

func (s *Streams) Master() uint64 { return s.master }

// Get returns a generator for (component, instance). Callers must hold on to
// the generator: creating a fresh one mid-run restarts the sequence.
func (s *Streams) Get(c Component, instance uint64) *rand.Rand {
	return rand.New(rand.NewSource(Derive(s.master, c, instance)))
}
