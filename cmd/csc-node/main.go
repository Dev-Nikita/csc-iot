// Command csc-node runs one role of the distributed topology.
//
// One binary, one role per process, one container per process. Separate roles
// as separate OS processes is the property that matters -- concurrency the Go
// runtime does not schedule, and a transport that can reorder and delay -- and
// that is what a role flag gives. Separate binaries would add build surface
// without adding a single scheduling boundary.
//
// Ingress (device -> gateway) is a direct TCP path, deliberately NOT on the
// bus: kernel impairment belongs to the radio-facing link, and REROUTE changes
// the gateway-to-edge compute assignment without touching it.
package main

import (
	"bufio"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"runtime"
	"slices"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
	"github.com/TODO-OWNER/csc-iot/internal/epoch"
	"github.com/TODO-OWNER/csc-iot/internal/fingerprint"
	"github.com/TODO-OWNER/csc-iot/internal/nodestate"
)

type ingressEvent struct {
	EventID  string `json:"event_id"`
	DeviceID string `json:"device_id"`
	Seq      uint64 `json:"seq"`
	Tick     int64  `json:"logical_tick"`
	// EmitUnixNanos is the wall-clock instant the device simulator emitted the
	// event. It exists so that end-to-end latency can be MEASURED rather than
	// counted in epochs.
	//
	// It is an observation, never state: it is not part of the structural
	// fingerprint and cannot affect the hash. Epoch-quantised waiting is exactly
	// reproducible, which is a virtue for the prefix and a defect for the
	// outcome -- quantising to logical time erases the timing variation that
	// impairment actually causes, so a replay dispersion measured on it is zero
	// for a reason that has nothing to do with the system being deterministic.
	EmitUnixNanos int64 `json:"emit_unix_nanos,omitempty"`
	// Marker closes an epoch IN BAND, on the data path itself.
	//
	// Without it the gateway declared its end-of-epoch sequence from the barrier
	// callback while its ingress reader was still a separate goroutine behind:
	// it announced a last_seq lower than what it would go on to publish, the
	// edge confirmed that lower number, and quiescence was satisfied with events
	// still in flight. Two runs then recorded 506 and 518 events consumed at the
	// same anchor. A side channel cannot tell a stage that a stream has ended;
	// only the stream can.
	Marker bool `json:"marker,omitempty"`
}

func main() {
	role := flag.String("role", "", "device-sim | gateway | edge | controller")
	id := flag.String("id", "", "node id, e.g. gw00")
	busAddr := flag.String("bus", "csc-broker:4300", "message bus address")
	busImpl := flag.String("bus-impl", "tcp", "transport implementation: tcp (development) | nats (requires -tags=nats)")
	ingress := flag.String("ingress", "", "gateway ingress address (device-sim dials, gateway listens)")
	rpcAddr := flag.String("rpc", "csc-intelligence:50051", "intelligence address (controller only)")
	route := flag.String("route", "edge00", "initial gateway->edge assignment (gateway only)")
	devices := flag.Int("devices", 100, "virtual devices (device-sim only)")
	rateHz := flag.Float64("rate-hz", 4, "per-device event rate")
	seed := flag.Uint64("seed", 42, "master seed")
	emitSpread := flag.Duration("emit-spread", 200*time.Millisecond,
		"device-sim: wall-clock window over which one epoch's events are emitted (0 = burst)")
	perEpoch := flag.Int("events-per-epoch", 200, "device-sim: events emitted per epoch (epoch-driven mode)")
	// Heterogeneous by configuration, not by accident: with equal capacity every
	// edge is interchangeable and REROUTE cannot change any outcome.
	servePerEpoch := flag.Int("serve-per-epoch", -1, "edge: events served per epoch (-1 = unbounded)")
	// The latency budget is a DECLARED parameter of the configuration, fixed
	// before any comparison is looked at and recorded in the manifest. It must
	// be chosen relative to the offered load: a budget every event violates
	// makes the failure term constant at 1 and blind to the action, and a budget
	// nothing violates makes it constant at 0.
	degradeAt := flag.Int64("degrade-at-epoch", 0, "edge: epoch at which capacity drops (0 = never)")
	degradedServe := flag.Int("degraded-serve-per-epoch", -1, "edge: capacity from -degrade-at-epoch onwards")
	slaMs := flag.Int64("sla-ms", 500, "edge: end-to-end latency budget in milliseconds (measured, not quantised)")
	slaEpochs := flag.Int64("sla-epochs", 1, "edge: an event waiting longer than this many epochs violates the agreement")
	version := flag.Bool("version", false, "print runtime build version and exit")
	flag.Parse()
	if *version {
		fmt.Printf("%s %s/%s\n", runtime.Version(), runtime.GOOS, runtime.GOARCH)
		return
	}

	if *role == "" || *id == "" {
		log.Fatal("both -role and -id are required")
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// device-sim also joins the bus, but only for the epoch barrier: its data
	// path stays the direct TCP ingress, which is what keeps netem off the
	// control plane. With -bus "" it runs free and is explicitly not replayable.
	var b bus.Bus
	if *busAddr != "" {
		var err error
		for i := 0; i < 40; i++ {
			b, err = bus.Dial(*busImpl, *busAddr, 2*time.Second)
			if err == nil {
				break
			}
			// A transport missing from this binary will never appear by
			// retrying: fail immediately rather than after ten seconds of
			// identical errors.
			if strings.Contains(err.Error(), "not compiled into this binary") {
				log.Fatalf("%s: %v", *id, err)
			}
			time.Sleep(250 * time.Millisecond)
		}
		if err != nil {
			log.Fatalf("%s: bus unreachable at %s: %v", *id, *busAddr, err)
		}
		defer b.Close()
		d := b.Descriptor()
		log.Printf("%s (%s) connected to bus %s [type=%s version=%s config=%s]",
			*id, *role, *busAddr, d.Type, d.Version, d.ConfigHash())
	}

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	switch *role {
	case "device-sim":
		runDeviceSim(ctx, *id, *ingress, *devices, *rateHz, *seed, *perEpoch, *emitSpread, b, sig)
	case "gateway":
		runGateway(ctx, *id, b, *ingress, *route, sig)
	case "edge":
		runEdge(ctx, *id, b, *servePerEpoch, *slaEpochs, *slaMs, *degradeAt, *degradedServe, sig)
	case "controller":
		runController(ctx, *id, b, *rpcAddr, sig)
	default:
		log.Fatalf("unknown role %q", *role)
	}
}

// joinEpochs makes a node a barrier participant. Roles do their per-epoch work
// in the callback; acknowledgement happens only after it returns, which is what
// makes "everyone finished tick k-1" mean something.
func joinEpochs(ctx context.Context, b bus.Bus, id string, work func(string, int64)) {
	if _, err := epoch.NewParticipant(ctx, b, id, work); err != nil {
		log.Fatalf("%s: epoch participation: %v", id, err)
	}
}

// --- device-sim: direct TCP ingress, the only impaired path ------------------

func runDeviceSim(ctx context.Context, id, ingress string, devices int, rateHz float64,
	seed uint64, perEpoch int, emitSpread time.Duration, b bus.Bus, sig chan os.Signal) {
	if ingress == "" {
		log.Fatal("device-sim needs -ingress")
	}
	var conn net.Conn
	var err error
	for i := 0; i < 60; i++ {
		conn, err = net.DialTimeout("tcp", ingress, 2*time.Second)
		if err == nil {
			break
		}
		time.Sleep(500 * time.Millisecond)
	}
	if err != nil {
		log.Fatalf("%s: ingress unreachable at %s: %v", id, ingress, err)
	}
	defer conn.Close()

	enc := json.NewEncoder(conn)
	var seq uint64

	// Epoch-driven, not clock-driven.
	//
	// The first M2' run measured two executions from the same prefix
	// specification diverging by ~25 events in ~10,140 -- 0.25%. The cause was
	// not the transport: device-sim emitted on a wall-clock ticker, so how many
	// events existed when the anchor was taken depended on how fast the machine
	// happened to be. No amount of fingerprint precision can fix a workload
	// whose size is a function of real time.
	//
	// Each epoch now emits exactly perEpoch events and only then acknowledges,
	// so the event count at epoch k is a property of k.
	if b != nil {
		joinEpochs(ctx, b, id, func(_ string, k int64) {
			// Events are PACED across the epoch, not fired as one burst.
			//
			// A burst gives every event of an epoch almost the same end-to-end
			// latency, so the whole batch crosses the latency budget together
			// and the violated fraction moves in steps of one epoch's worth of
			// events. Measured on the pilot: within a cell nothing varied except
			// the violation count, which flipped between exactly 400 and 500 --
			// one batch of 100 sitting on the threshold. That step, not the
			// system, was the replay dispersion.
			//
			// Devices in a real deployment do not emit simultaneously either, so
			// pacing is the more faithful workload as well as the better
			// instrument. The COUNT per epoch is unchanged and still exact, so
			// the prefix stays reproducible; only the arrival times within the
			// epoch spread out.
			var gap time.Duration
			if emitSpread > 0 && perEpoch > 1 {
				gap = emitSpread / time.Duration(perEpoch)
			}
			for i := 0; i < perEpoch; i++ {
				seq++
				if err := enc.Encode(ingressEvent{
					EventID:  fmt.Sprintf("%s-e%08d", id, seq),
					DeviceID: fmt.Sprintf("dev%05d", seq%uint64(devices)),
					Seq:      seq, Tick: k, EmitUnixNanos: time.Now().UnixNano(),
				}); err != nil {
					log.Printf("%s: ingress write failed at epoch %d: %v", id, k, err)
					return
				}
				if gap > 0 {
					time.Sleep(gap)
				}
			}
			// The marker rides the same socket behind the epoch's events, so a
			// gateway that has seen it has necessarily seen all of them.
			if err := enc.Encode(ingressEvent{
				EventID: fmt.Sprintf("%s-mark-%d", id, k), Seq: seq, Tick: k, Marker: true,
			}); err != nil {
				log.Printf("%s: epoch marker %d failed: %v", id, k, err)
			}
		})
		if err := nodestate.Serve(ctx, b, id, "device-sim", func(int64) nodestate.Report {
			return nodestate.Report{SeqPositions: map[string]uint64{"emitted": seq}}
		}); err != nil {
			log.Fatalf("%s: fingerprint service: %v", id, err)
		}
		log.Printf("%s: %d devices -> %s, %d events per epoch (epoch-driven)", id, devices, ingress, perEpoch)
		<-sig
		log.Printf("%s: stopping after %d events", id, seq)
		return
	}

	// No bus: free-running mode for the topology smoke test, where only
	// end-to-end flow is being checked and determinism is not claimed.
	log.Printf("%s: %d devices -> %s at %.1f Hz each (free-running, NOT replayable)",
		id, devices, ingress, rateHz)
	period := time.Duration(float64(time.Second) / (rateHz * float64(devices)))
	if period < time.Millisecond {
		period = time.Millisecond
	}
	tk := time.NewTicker(period)
	defer tk.Stop()
	tick := int64(0)
	for {
		select {
		case <-sig:
			log.Printf("%s: stopping after %d events", id, seq)
			return
		case <-ctx.Done():
			return
		case <-tk.C:
			seq++
			if seq%uint64(devices) == 0 {
				tick++
			}
			if err := enc.Encode(ingressEvent{
				EventID:  fmt.Sprintf("%s-e%08d", id, seq),
				DeviceID: fmt.Sprintf("dev%05d", seq%uint64(devices)),
				Seq:      seq, Tick: tick,
			}); err != nil {
				log.Printf("%s: ingress write failed: %v", id, err)
				return
			}
		}
	}
}

// --- gateway: accepts ingress, forwards to an edge over the bus --------------

func runGateway(ctx context.Context, id string, b bus.Bus, ingress, route string, sig chan os.Signal) {
	// The routing table is real state: the gateway publishes to the subject of
	// the edge it currently routes to, so REROUTE moves traffic rather than
	// updating a map nothing reads.
	var routeTo atomic.Value
	routeTo.Store(route)

	// THROTTLE is an admission limit with a real backlog, not a flag.
	//
	// An action that executes without mutating state is inert, and an inert
	// branch cannot differ from NO_OP for any reason the methodology can name.
	// A throttled gateway admits at most admitCap events per epoch and defers
	// the rest; the deferred events are queue state, they are drained at the
	// start of the next epoch, and they appear in the structural fingerprint by
	// content, so a deferral changes the future exactly as much as it really does.
	var admitCap atomic.Int64
	admitCap.Store(-1) // unlimited
	var admitMu sync.Mutex
	var admittedThisEpoch int64
	var backlog []ingressEvent
	// Measured outcomes, not structural state. The gateway is the only place
	// that knows how much work the system was ASKED to handle: work refused
	// admission never reaches an edge, so an edge-side denominator silently
	// shrinks under THROTTLE and flatters exactly the action under test.
	// These counters are reported in Observed and are never hashed.
	var ingressAccepted atomic.Int64
	var deferredTotal atomic.Int64
	var currentRun atomic.Value
	currentRun.Store("")
	// Assigned below, once the sequence counter it advances exists; every call
	// site runs after that assignment.
	var forward func(ingressEvent)
	if ingress == "" {
		ingress = ":5000"
	}
	ln, err := net.Listen("tcp", ingress)
	if err != nil {
		log.Fatalf("%s: cannot listen on %s: %v", id, ingress, err)
	}
	defer ln.Close()
	log.Printf("%s: ingress on %s, routing to %s", id, ln.Addr(), route)

	// Control plane: a REROUTE action retargets this gateway.
	if err := b.Subscribe(ctx, bus.SubjectControllerActions, func(e bus.Envelope) {
		var act bus.ActionCommand
		if json.Unmarshal(e.Payload, &act) != nil || act.Target != id {
			return
		}
		ack := bus.ActionAck{
			RunID: act.RunID, ActionID: act.ActionID, Target: id,
			Action: act.Action,
		}
		activeRun := currentRun.Load().(string)
		manual := act.RunID == "manual" && activeRun == ""
		if act.RunID == "" || act.ActionID == "" || (!manual && act.RunID != activeRun) {
			ack.Detail = "run_id is empty or does not match the gateway's active epoch run"
		} else {
			switch {
			case act.Action == "REROUTE" && act.Edge != "":
				prev := routeTo.Load().(string)
				routeTo.Store(act.Edge)
				ack.Applied = true
				ack.Detail = fmt.Sprintf("route %s -> %s", prev, act.Edge)
				log.Printf("%s: REROUTE %s -> %s", id, prev, act.Edge)
			case act.Action == "THROTTLE":
				limit := act.Limit
				if limit <= 0 {
					limit = 1 // a throttle that admits everything is not a throttle
				}
				admitCap.Store(limit)
				ack.Applied = true
				ack.Detail = fmt.Sprintf("admit limit=%d", limit)
				log.Printf("%s: THROTTLE admit<=%d per epoch", id, limit)
			default:
				ack.Detail = "unsupported or incomplete action"
			}
		}
		payload, _ := json.Marshal(ack)
		_ = b.Publish(ctx, bus.SubjectControllerActionAcks, bus.Envelope{
			ExperimentID: act.RunID, LogicalTick: e.LogicalTick, ProducerID: id,
			EventID: act.ActionID + "-ack", Payload: payload,
		})
	}); err != nil {
		log.Fatalf("%s: action subscription: %v", id, err)
	}

	wm, err := epoch.NewWatermark(ctx, b, "", nil) // follower: the run comes from the declaration
	if err != nil {
		log.Fatalf("%s: watermark: %v", id, err)
	}
	var seq uint64
	var lastTick int64

	// The gateway's slice of the structural fingerprint. Sequence position is
	// the field that makes drain watermarks checkable, so it is reported exactly
	// rather than rounded to a tick.
	// marked carries the published sequence at which each epoch's ingress ended.
	marked := make(chan struct {
		epoch int64
		seq   uint64
	}, 64)

	// The barrier callback blocks until the epoch's marker has traversed the
	// ingress, so acknowledging epoch k means this gateway has published
	// everything belonging to k -- not merely that it was asked to stop.
	// A gateway nobody feeds has nothing to wait for. gw01 has an ingress
	// listener but no device-sim attached, and blocking it on a marker that will
	// never arrive stalled the whole barrier -- one idle node held up every
	// other. Waiting is conditional on actually having a producer.
	var hasIngress atomic.Bool

	joinEpochs(ctx, b, id, func(runID string, k int64) {
		// Bind before declaring: an end-of-epoch declaration must carry the run
		// it belongs to, or a consumer cannot tell it from last run's.
		wm.SetRun(runID)
		currentRun.Store(runID)

		// A new epoch restores the admission budget, and deferred work goes
		// first: a backlog that were never drained would be an outage, not a
		// throttle.
		cap := admitCap.Load()
		admitMu.Lock()
		admittedThisEpoch = 0
		var drain []ingressEvent
		for len(backlog) > 0 && (cap < 0 || admittedThisEpoch < cap) {
			drain = append(drain, backlog[0])
			backlog = backlog[1:]
			admittedThisEpoch++
		}
		admitMu.Unlock()
		for _, ev := range drain {
			forward(ev)
		}
		if !hasIngress.Load() {
			_ = wm.DeclareEnd(ctx, k, id, bus.EdgeWorkSubject(routeTo.Load().(string)), atomic.LoadUint64(&seq))
			return
		}
		// Shorter than the orchestrator's barrier timeout on purpose: a late
		// marker should surface as a flagged declaration here, not as a barrier
		// failure that names the wrong culprit.
		deadline := time.After(5 * time.Second)
		for {
			select {
			case m := <-marked:
				if m.epoch < k {
					continue // a straggler from an earlier epoch
				}
				_ = wm.DeclareEnd(ctx, k, id, bus.EdgeWorkSubject(routeTo.Load().(string)), m.seq)
				return
			case <-deadline:
				log.Printf("%s: epoch %d marker never arrived; declaring at %d and flagging it",
					id, k, atomic.LoadUint64(&seq))
				_ = wm.DeclareEnd(ctx, k, id, bus.EdgeWorkSubject(routeTo.Load().(string)), atomic.LoadUint64(&seq))
				return
			case <-ctx.Done():
				return
			}
		}
	})

	if err := nodestate.Serve(ctx, b, id, "gateway", func(int64) nodestate.Report {
		admitMu.Lock()
		ids := make([]string, 0, len(backlog))
		for _, ev := range backlog {
			ids = append(ids, ev.EventID)
		}
		depth := float64(len(backlog))
		admitMu.Unlock()
		limit := float64(admitCap.Load())
		return nodestate.Report{
			Routing: map[string]string{"edge": routeTo.Load().(string)},
			// The admission LIMIT is future-relevant: THROTTLE changes it and it
			// governs every later epoch. The count admitted SO FAR in the current
			// epoch is not: the budget is restored at the next epoch boundary,
			// before anything further is admitted. Reporting it made two prefixes
			// that behave identically hash differently -- a false divergence, and
			// the more dangerous kind, because it inflates measured
			// nondeterminism rather than hiding it.
			RateLimits:   map[string]float64{"admit": limit},
			Queues:       map[string]fingerprint.Queue{"admission_backlog": fingerprint.HashQueue(ids)},
			SeqPositions: map[string]uint64{"published": atomic.LoadUint64(&seq)},
			// Never hashed. admission_backlog_depth is the residual at report
			// time -- work the branch accepted and never delivered.
			Observed: map[string]float64{
				"ingress_accepted":         float64(ingressAccepted.Load()),
				"admission_deferred_total": float64(deferredTotal.Load()),
				"admission_backlog_depth":  depth,
			},
		}
	}); err != nil {
		log.Fatalf("%s: fingerprint service: %v", id, err)
	}

	forward = func(ev ingressEvent) {
		n := atomic.AddUint64(&seq, 1)
		payload, _ := json.Marshal(ev)
		target := bus.EdgeWorkSubject(routeTo.Load().(string))
		_ = b.Publish(ctx, target, bus.Envelope{
			LogicalTick: ev.Tick, ProducerID: id, Seq: n,
			EventID: ev.EventID, Payload: payload,
		})
	}

	go func() {
		for {
			c, err := ln.Accept()
			if err != nil {
				return
			}
			hasIngress.Store(true)
			go func(c net.Conn) {
				defer c.Close()
				dec := json.NewDecoder(bufio.NewReaderSize(c, 1<<16))
				for {
					var ev ingressEvent
					if err := dec.Decode(&ev); err != nil {
						return
					}
					if ev.Marker {
						select {
						case marked <- struct {
							epoch int64
							seq   uint64
						}{ev.Tick, atomic.LoadUint64(&seq)}:
						default:
						}
						continue
					}
					ingressAccepted.Add(1)
					cap := admitCap.Load()
					admitMu.Lock()
					deferred := cap >= 0 && admittedThisEpoch >= cap
					if deferred {
						backlog = append(backlog, ev)
					} else {
						admittedThisEpoch++
					}
					admitMu.Unlock()
					if deferred {
						deferredTotal.Add(1)
					}
					if deferred {
						continue
					}
					forward(ev)
					atomic.StoreInt64(&lastTick, ev.Tick)
				}
			}(c)
		}
	}()

	report := time.NewTicker(5 * time.Second)
	defer report.Stop()
	for {
		select {
		case <-sig:
			log.Printf("%s: forwarded %d events", id, atomic.LoadUint64(&seq))
			return
		case <-report.C:
			log.Printf("%s: forwarded=%d tick=%d", id, atomic.LoadUint64(&seq), atomic.LoadInt64(&lastTick))
		}
	}
}

// --- edge: consumes work, confirms drain, publishes telemetry ---------------

// runEdge consumes work at a bounded rate.
//
// Until now an edge consumed everything the instant it arrived, which made all
// three edges interchangeable: REROUTE moved traffic to a node that behaved
// identically, so the action could not change any outcome and measured exactly
// zero effect by construction. An edge now serves at most servePerEpoch events
// per epoch and queues the rest, so a slow or loaded edge builds a real backlog
// and moving work off it is a real intervention.
//
// Waiting is counted in EPOCHS, not wall-clock: an event's latency is the
// number of epoch boundaries between its arrival and its service. Wall-clock
// latency would vary with machine load and would put a nondeterministic
// quantity next to state that must match exactly.
func runEdge(ctx context.Context, id string, b bus.Bus, servePerEpoch int, slaEpochs, slaMs int64,
	degradeAt int64, degradedServe int, sig chan os.Signal) {
	wm, err := epoch.NewWatermark(ctx, b, "", []string{id}) // follower
	if err != nil {
		log.Fatalf("%s: watermark: %v", id, err)
	}
	var processed uint64 // served, not merely received
	var mu sync.Mutex
	through := map[string]uint64{}

	type queued struct {
		eventID  string
		arrivedK int64
		emitNs   int64
	}
	var inbox []queued
	var currentEpoch int64
	var served, violations, waitSum, waitMax float64
	var latSum, latMax, latViolations float64

	if err := b.Subscribe(ctx, bus.EdgeWorkSubject(id), func(e bus.Envelope) {
		var ev ingressEvent
		_ = json.Unmarshal(e.Payload, &ev)
		mu.Lock()
		// Arrival is not service. The drain watermark still advances on arrival,
		// because it answers "has the transport delivered everything", which is
		// a different question from "has this node finished the work".
		inbox = append(inbox, queued{eventID: e.EventID, arrivedK: currentEpoch, emitNs: ev.EmitUnixNanos})
		if e.Seq > through[e.ProducerID] {
			through[e.ProducerID] = e.Seq
		}
		mu.Unlock()
	}); err != nil {
		log.Fatalf("%s: subscribe: %v", id, err)
	}
	if err := b.Subscribe(ctx, epoch.SubjectEndEpoch, func(e bus.Envelope) {
		var d epoch.EndEpoch
		if json.Unmarshal(e.Payload, &d) != nil {
			return
		}
		// Only the declarations this edge is the consumer of. Answering
		// another edge's subject wrote entries like drained:edge01:gw00 = 0
		// into the anchor: residue that looks like an unmet requirement.
		if c := epoch.SubjectConsumer(d.Subject); c != nil && !slices.Contains(c, id) {
			return
		}
		if d.RunID != "" {
			wm.SetRun(d.RunID)
		}
		// Confirming whatever had arrived at the instant the declaration was
		// read is what produced an accepted anchor recording 1866 consumed of
		// 2000 declared: the producer's last event was still in flight, and the
		// edge answered "drained" for a queue it had not finished. The
		// confirmation waits for the declared sequence.
		//
		// Publishing intermediate positions as they are reached is safe because
		// the watermark is monotonic, and it keeps a stalled drain legible
		// instead of silent.
		go func() {
			deadline := time.Now().Add(30 * time.Second)
			var reported uint64
			var everReported bool
			for {
				mu.Lock()
				got := through[d.ProducerID]
				mu.Unlock()
				// An idle producer declares its end at sequence 0 and its
				// consumer must still say so: "nothing was sent" and "nothing
				// was confirmed" are not the same state.
				if got > reported || !everReported {
					_ = wm.ConfirmDrained(ctx, d.Epoch, id, d.ProducerID, d.Subject, got)
					reported, everReported = got, true
				}
				if got >= d.LastSeq {
					return
				}
				if time.Now().After(deadline) {
					// Deliberately left short of the declaration. The
					// orchestrator refuses the anchor; a confirmation forged up
					// to LastSeq here would hide the defect in the evidence.
					log.Printf("%s: epoch %d: %s drained only %d of %d",
						id, d.Epoch, d.ProducerID, got, d.LastSeq)
					return
				}
				select {
				case <-ctx.Done():
					return
				case <-time.After(5 * time.Millisecond):
				}
			}
		}()
	}); err != nil {
		log.Fatalf("%s: subscribe end-epoch: %v", id, err)
	}
	joinEpochs(ctx, b, id, func(runID string, k int64) {
		wm.SetRun(runID)

		// Service happens on the epoch boundary, in logical time, so what a
		// branch produced is a function of the epoch schedule rather than of
		// how fast this container happened to run.
		mu.Lock()
		currentEpoch = k
		budget := servePerEpoch
		// A fault is a real capacity loss at a declared logical time, not a
		// label. Without one the system is either always healthy or always
		// broken, and a controller that prevents failures has nothing to
		// prevent: every anchor sits at the same point of the same ramp.
		if degradeAt > 0 && k >= degradeAt && degradedServe >= 0 {
			budget = degradedServe
		}
		for budget != 0 && len(inbox) > 0 {
			item := inbox[0]
			inbox = inbox[1:]
			wait := float64(k - item.arrivedK)
			served++
			waitSum += wait
			if wait > waitMax {
				waitMax = wait
			}
			if int64(wait) > slaEpochs {
				violations++
			}
			if item.emitNs > 0 {
				ms := float64(time.Now().UnixNano()-item.emitNs) / 1e6
				latSum += ms
				if ms > latMax {
					latMax = ms
				}
				if ms > float64(slaMs) {
					latViolations++
				}
			}
			atomic.AddUint64(&processed, 1)
			if budget > 0 {
				budget--
			}
		}
		mu.Unlock()

		n := atomic.LoadUint64(&processed)
		payload, _ := json.Marshal(map[string]any{"processed": n, "epoch": k})
		_ = b.Publish(ctx, bus.SubjectEdgeTelemetry, bus.Envelope{
			LogicalTick: k, ProducerID: id,
			EventID: fmt.Sprintf("%s-tel-%d", id, k), Payload: payload,
		})
	})

	if err := nodestate.Serve(ctx, b, id, "edge", func(int64) nodestate.Report {
		mu.Lock()
		seqs := make(map[string]uint64, len(through))
		for k, v := range through {
			seqs[k] = v
		}
		ids := make([]string, 0, len(inbox))
		var eligible float64
		for _, q := range inbox {
			ids = append(ids, q.eventID)
			// Work that arrived during the epoch being read has not yet had a
			// service opportunity: the next boundary is where it would be
			// served. Counting it as unserved charges the branch for the fact
			// that the run ended, which is a property of the horizon and not of
			// the action.
			if q.arrivedK < currentEpoch {
				eligible++
			}
		}
		obs := map[string]float64{
			"served": served, "sla_violations": violations,
			"wait_sum_epochs": waitSum, "wait_max_epochs": waitMax,
			"unserved":          float64(len(inbox)),
			"lat_ms_sum":        latSum,
			"lat_ms_max":        latMax,
			"lat_ms_violations": latViolations,
		}
		mu.Unlock()
		// The inbox is reported BY CONTENT. Two edges holding the same number of
		// different events have different futures, and with a real service rate
		// that difference is now reachable.
		return nodestate.Report{
			Queues: map[string]fingerprint.Queue{"inbox": fingerprint.HashQueue(ids)},
			EdgeCapacity: map[string]float64{
				"serve_per_epoch":  float64(servePerEpoch),
				"degrade_at_epoch": float64(degradeAt),
				"degraded_serve":   float64(degradedServe),
			},
			SeqPositions:    seqs,
			ProcessedCounts: map[string]int64{"processed": int64(atomic.LoadUint64(&processed))},
			Observed:        obs,
		}
	}); err != nil {
		log.Fatalf("%s: fingerprint service: %v", id, err)
	}
	log.Printf("%s: consuming %s", id, bus.EdgeWorkSubject(id))

	// Telemetry is emitted once per epoch, not on a wall-clock ticker: how many
	// samples exist by a given anchor must be a property of the epoch, not of
	// how fast the machine ran.
	<-sig
	log.Printf("%s: processed %d", id, atomic.LoadUint64(&processed))
}

// --- controller: watches telemetry, calls the intelligence plane ------------

func runController(ctx context.Context, id string, b bus.Bus, rpcAddr string, sig chan os.Signal) {
	var seen uint64
	if err := b.Subscribe(ctx, bus.SubjectEdgeTelemetry, func(bus.Envelope) {
		atomic.AddUint64(&seen, 1)
	}); err != nil {
		log.Fatalf("%s: subscribe: %v", id, err)
	}
	joinEpochs(ctx, b, id, func(string, int64) {})

	// The controller reports nothing structural. Its count of telemetry samples
	// does not influence how the system evolves, and the rule cuts both ways:
	// everything future-relevant must be in the fingerprint, and nothing else
	// may be -- a field that varies without changing the future would abort
	// branch sets for no reason.
	if err := nodestate.Serve(ctx, b, id, "controller", func(int64) nodestate.Report {
		return nodestate.Report{}
	}); err != nil {
		log.Fatalf("%s: fingerprint service: %v", id, err)
	}
	log.Printf("%s: watching telemetry, intelligence at %s", id, rpcAddr)

	tk := time.NewTicker(3 * time.Second)
	defer tk.Stop()
	for {
		select {
		case <-sig:
			return
		case <-tk.C:
			log.Printf("%s: telemetry samples=%d (decision loop wired in M2')", id, atomic.LoadUint64(&seen))
		}
	}
}
