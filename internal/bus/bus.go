// Package bus is the transport abstraction for the distributed substrate.
//
// Why an interface rather than a direct NATS dependency: the build environment
// used for A0/M2 cannot reach the Go module proxy, so nats.go can be written but
// not compiled, race-tested, or exercised for reconnect, ordering, shutdown and
// backpressure. Shipping untested transport code would break the rule this
// project runs on. The first adapter is therefore stdlib TCP -- separate OS
// processes, real sockets, real kernel scheduling -- and a NATS adapter
// implements the same contract once it can actually be tested.
//
// This distinction is not cosmetic. The replay resolution eta_J is a property of
// a concrete runtime stack: transport, buffering, scheduling and backpressure
// all shape it. An eta_J measured over the stdlib broker does not transfer to a
// NATS deployment, and the manifest records which stack produced it.
package bus

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
)

// Subjects carried by the bus. Device-to-gateway ingress is NOT here: it runs
// over a direct TCP path so that F1/F2 impairment applies to the radio-facing
// link, while REROUTE changes the gateway-to-edge compute assignment and leaves
// that impairment untouched. Routing both over one bus would reintroduce the
// mismatch M2 exposed between the manuscript's SCM and the implementation.
const (
	// SubjectEdgeWork is a PREFIX. Work is published to edge.work.<edgeID> and
	// each edge subscribes to its own subject.
	//
	// Broadcasting to one shared subject would have every edge process every
	// event, which makes the routing table decorative -- and REROUTE, the action
	// the paper is largely about, would change a map that no packet consults.
	// The topology smoke test caught exactly this: three edges each processed
	// ~2865 of the same 1679 forwarded events.
	SubjectEdgeWork          = "edge.work"
	SubjectGatewayTelemetry  = "gateway.telemetry"
	SubjectEdgeTelemetry     = "edge.telemetry"
	SubjectControllerActions    = "controller.actions"
	SubjectControllerActionAcks = "controller.actions.ack"
	SubjectEpoch             = "experiment.epoch"
	SubjectEpochAck          = "experiment.epoch.ack"
)

// Envelope carries the identity every message needs for trace alignment,
// deduplication, replay matching and fingerprinting.
//
// These fields are deliberately NOT used to globally reorder the live stream
// into a deterministic sequence. Where queueing semantics depend on arrival
// order, real arrival order is preserved: reordering everything would erase the
// nondeterminism D0 exists to measure and quietly turn the distributed system
// back into a deterministic emulator.
type Envelope struct {
	ExperimentID string `json:"experiment_id"`
	LogicalTick  int64  `json:"logical_tick"`
	ProducerID   string `json:"producer_id"`
	Seq          uint64 `json:"seq"`
	EventID      string `json:"event_id"`
	Subject      string `json:"subject"`
	Payload      []byte `json:"payload"`
}

// Handler consumes a delivered envelope. It must not block the reader.
type Handler func(Envelope)

// Bus is the contract every transport adapter implements.
type Bus interface {
	Publish(ctx context.Context, subject string, env Envelope) error
	Subscribe(ctx context.Context, subject string, h Handler) error
	Close() error
	// Descriptor identifies the concrete transport for the run manifest.
	Descriptor() Descriptor
}

// Descriptor names the transport in a way a manifest can record and a reader
// can check. eta_J is only comparable across runs sharing one descriptor.
type Descriptor struct {
	Type    string            `json:"bus_type"`
	Version string            `json:"bus_version"`
	Config  map[string]string `json:"transport_config"`
}

// EdgeWorkSubject is the per-edge work subject a gateway publishes to.
func EdgeWorkSubject(edgeID string) string { return SubjectEdgeWork + "." + edgeID }

// ConfigHash fingerprints the transport configuration.
func (d Descriptor) ConfigHash() string {
	keys := make([]string, 0, len(d.Config))
	for k := range d.Config {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	h := sha256.New()
	fmt.Fprintf(h, "%s|%s|", d.Type, d.Version)
	for _, k := range keys {
		fmt.Fprintf(h, "%s=%s;", k, d.Config[k])
	}
	return hex.EncodeToString(h.Sum(nil))[:16]
}
