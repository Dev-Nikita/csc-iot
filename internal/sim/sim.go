// Package sim is the Phase A execution core: devices, gateways, edge nodes and
// a tick loop, all driven by the experiment clock and per-component RNG
// streams.
//
// Scope, stated plainly: this is an in-process discrete-time emulation. Queues,
// routing tables and rate limiters are real mutable state and recovery actions
// change that state, so downstream effects follow from the model's own dynamics
// rather than from an assumed effect size. It is NOT yet the distributed
// deployment described in ARCHITECTURE.md -- there is no NATS, no gRPC and no
// kernel netem here, and runs produced by this core are labelled
// impairment_mode = application_layer for exactly that reason.
package sim

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"math"
	"math/rand"
	"sort"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/clock"
	"github.com/TODO-OWNER/csc-iot/internal/config"
	"github.com/TODO-OWNER/csc-iot/internal/faults"
	"github.com/TODO-OWNER/csc-iot/internal/rng"
	"github.com/TODO-OWNER/csc-iot/internal/routing"
	"github.com/TODO-OWNER/csc-iot/internal/telemetry"
)

type Device struct {
	ID        string
	X, Y      float64
	VX, VY    float64
	RateHz    float64
	GatewayID string
	rnd       *rand.Rand
}

type Gateway struct {
	ID      string
	X, Y    float64
	Queue   int
	Retries int64
}

type Edge struct {
	ID         string
	Queue      int
	Served     int64
	Dropped    int64
	CapacityHz float64
}

// Action is a recovery primitive. Phase A implements the three that are
// straightforwardly deterministic; MIGRATE and REPLICATE arrive after replay is
// stable, with their state-transfer and cold-start costs modelled rather than
// subtracted from a latency variable.
type Action string

const (
	NoOp     Action = "NO_OP"
	Reroute  Action = "REROUTE"
	Throttle Action = "THROTTLE"
	// Release undoes a throttle. A controller that can enter a mitigation but
	// never leave it is not a fair baseline.
	Release Action = "RELEASE"
)

// Controller observes the current view and returns an action plus a target.
type Controller interface {
	Name() string
	Decide(v View, rnd *rand.Rand) (Action, string, float64)
}

// View is what a controller sees at a decision tick.
type View struct {
	ElapsedS      float64
	QueueDepth    map[string]int
	Load          map[string]float64
	LossRatio     float64
	RTTMs         float64
	RetryRate     float64
	E2ELatencyMs  float64
	DeliveryRatio float64
	Routes        map[string]string
	Throttles     map[string]float64
	Edges         []string
	Gateways      []string
}

type Engine struct {
	cfg      config.Config
	clk      *clock.Clock
	streams  *rng.Streams
	sched    *faults.Schedule
	table    *routing.Table
	devices  []*Device
	gateways []*Gateway
	edges    []*Edge
	ctrl     Controller
	ctrlRnd  *rand.Rand

	sent, delivered, retried, violations int64
	// Counted over the measurement window only. Warm-up transients would
	// otherwise be scored as SLA violations in every run and inflate every
	// controller's failure count equally but meaninglessly.
	winSent, winDelivered int64
	measuring             bool
	holdTicks             int
	lastLatency           float64
	lastDelivery          float64
	// history is per-engine on purpose: a package-level slice would leak state
	// between runs in the same process and silently break determinism.
	history []string
}

func New(cfg config.Config, ctrl Controller) (*Engine, error) {
	if err := cfg.Validate(); err != nil {
		return nil, err
	}
	st := rng.New(cfg.MasterSeed)
	e := &Engine{
		cfg:     cfg,
		clk:     clock.New(time.Duration(cfg.Timing.TelemetryMs) * time.Millisecond),
		streams: st,
		sched:   faults.New(cfg.Scenario),
		ctrl:    ctrl,
		ctrlRnd: st.Get(rng.Controller, 0),
	}
	gwIDs := make([]string, cfg.Topology.Gateways)
	for i := range gwIDs {
		gwIDs[i] = fmt.Sprintf("gw%02d", i)
		mob := st.Get(rng.Mobility, uint64(1000+i))
		e.gateways = append(e.gateways, &Gateway{ID: gwIDs[i], X: mob.Float64() * 1000, Y: mob.Float64() * 1000})
	}
	edgeIDs := make([]string, cfg.Topology.Edges)
	for i := range edgeIDs {
		edgeIDs[i] = fmt.Sprintf("edge%02d", i)
		e.edges = append(e.edges, &Edge{ID: edgeIDs[i], CapacityHz: cfg.EdgeCapacityHz})
	}
	e.table = routing.NewTable(gwIDs, edgeIDs)

	for i := 0; i < cfg.Topology.Devices; i++ {
		wr := st.Get(rng.Workload, uint64(i))
		mo := st.Get(rng.Mobility, uint64(i))
		d := &Device{
			ID:     fmt.Sprintf("dev%05d", i),
			X:      mo.Float64() * 1000,
			Y:      mo.Float64() * 1000,
			VX:     (mo.Float64() - 0.5) * 4,
			VY:     (mo.Float64() - 0.5) * 4,
			RateHz: cfg.EventRateHz * (0.75 + 0.5*wr.Float64()),
			rnd:    wr,
		}
		d.GatewayID = e.nearestGateway(d)
		e.devices = append(e.devices, d)
	}
	return e, nil
}

func (e *Engine) nearestGateway(d *Device) string {
	best, bestD := e.gateways[0].ID, math.Inf(1)
	for _, g := range e.gateways {
		dist := math.Hypot(d.X-g.X, d.Y-g.Y)
		if dist < bestD {
			best, bestD = g.ID, dist
		}
	}
	return best
}

// linkQuality maps distance and impairment to an abstract [0,1] score.
// It is not a measured radio SINR and is never described as one.
func linkQuality(distance float64, l faults.Link) float64 {
	q := 1.0 - math.Min(1, distance/1400)
	q *= 1.0 - l.LossRatio
	return math.Max(0, math.Min(1, q))
}

// Run executes warmup + measurement + cooldown and returns summary counters.
func (e *Engine) Run(tw, dw *telemetry.Writer) (map[string]int64, error) {
	total := e.cfg.Timing.WarmupS + e.cfg.Timing.MeasureS + e.cfg.Timing.CooldownS
	ticks := total * 1000 / e.cfg.Timing.TelemetryMs
	ctrlEvery := e.cfg.Timing.TickMs / e.cfg.Timing.TelemetryMs
	dtS := float64(e.cfg.Timing.TelemetryMs) / 1000

	netRnd := e.streams.Get(rng.Network, 0)
	svcRnd := e.streams.Get(rng.Service, 0)

	for tick := 0; tick < ticks; tick++ {
		elapsed := float64(tick) * dtS
		warm := float64(e.cfg.Timing.WarmupS)
		e.measuring = elapsed >= warm && elapsed < warm+float64(e.cfg.Timing.MeasureS)
		e.step(tick, elapsed, dtS, netRnd, svcRnd, tw)
		if ctrlEvery > 0 && tick%ctrlEvery == 0 && elapsed >= float64(e.cfg.Timing.WarmupS) {
			if _, err := e.control(tick, elapsed, dw); err != nil {
				return nil, err
			}
		}
		e.clk.Advance()
	}
	return map[string]int64{
		"events_sent": e.sent, "events_delivered": e.delivered,
		"window_events_sent": e.winSent, "window_events_delivered": e.winDelivered,
		"retries": e.retried, "sla_violation_ticks": e.violations,
	}, nil
}

func (e *Engine) step(tick int, elapsed, dtS float64, netRnd, svcRnd *rand.Rand, tw *telemetry.Writer) {
	byGW := map[string]int{}
	var lossSum, rttSum, qSum float64

	// --- devices generate, gateways admit ---------------------------------
	for _, d := range e.devices {
		d.X += d.VX * dtS
		d.Y += d.VY * dtS
		if d.X < 0 || d.X > 1000 {
			d.VX = -d.VX
		}
		if d.Y < 0 || d.Y > 1000 {
			d.VY = -d.VY
		}
		d.GatewayID = e.nearestGateway(d)

		want := d.RateHz * dtS
		n := int(want)
		if d.rnd.Float64() < want-float64(n) {
			n++
		}
		admitted := 0
		thr := e.table.ThrottleFor(d.GatewayID)
		for i := 0; i < n; i++ {
			if d.rnd.Float64() <= thr {
				admitted++
			}
		}
		e.sent += int64(n)
		if e.measuring {
			e.winSent += int64(n)
		}
		byGW[d.GatewayID] += admitted
	}

	// --- links: loss causes retransmission, not silent disappearance ------
	for _, g := range e.gateways {
		l := e.sched.At(elapsed, g.ID)
		lossSum += l.LossRatio
		rttSum += 10 + l.ExtraRTTMs
		arrivals := byGW[g.ID]
		lost := 0
		for i := 0; i < arrivals; i++ {
			if netRnd.Float64() < l.LossRatio {
				lost++
			}
		}
		g.Retries += int64(lost)
		e.retried += int64(lost)
		// retries re-enter the queue: this is the amplification path F7 will use
		g.Queue += arrivals + lost
		edgeID := e.table.EdgeFor(g.ID)
		for _, ed := range e.edges {
			if ed.ID == edgeID {
				ed.Queue += g.Queue
				g.Queue = 0
			}
		}
	}

	// --- edges serve at capacity -----------------------------------------
	var latSum float64
	for _, ed := range e.edges {
		capacity := int(ed.CapacityHz*dtS + svcRnd.Float64()*0.5)
		served := ed.Queue
		if served > capacity {
			served = capacity
		}
		ed.Queue -= served
		ed.Served += int64(served)
		if ed.Queue > e.cfg.QueueLimit {
			ed.Dropped += int64(ed.Queue - e.cfg.QueueLimit)
			ed.Queue = e.cfg.QueueLimit
		}
		e.delivered += int64(served)
		if e.measuring {
			e.winDelivered += int64(served)
		}
		qSum += float64(ed.Queue)
		// queueing delay by Little's law plus a fixed service time
		latSum += float64(ed.Queue)/math.Max(1, ed.CapacityHz)*1000 + 5
	}

	nG, nE := float64(len(e.gateways)), float64(len(e.edges))
	e.lastLatency = latSum/nE + rttSum/nG
	// Delivery ratio is measured over the measurement window, not cumulatively
	// from t=0: a cumulative ratio never recovers from the warm-up fill and
	// would report a violation forever.
	switch {
	case e.measuring && e.winSent > 0:
		e.lastDelivery = float64(e.winDelivered) / float64(e.winSent)
	case e.sent > 0:
		e.lastDelivery = float64(e.delivered) / float64(e.sent)
	default:
		e.lastDelivery = 1
	}
	violated := e.lastLatency > e.cfg.SLA.MaxE2ELatencyMs || e.lastDelivery < e.cfg.SLA.MinDeliveryRatio
	if violated {
		e.holdTicks++
		if e.measuring && e.holdTicks >= e.cfg.SLA.ViolationHoldTicks {
			e.violations++
		}
	} else {
		e.holdTicks = 0
	}

	if tw != nil {
		st := e.clk.Stamp()
		for _, ed := range e.edges {
			_ = tw.Write(telemetry.Sample{
				Stamp: st, NodeID: ed.ID, NodeType: "edge",
				QueueDepth: ed.Queue, Load: float64(ed.Queue) / float64(e.cfg.QueueLimit),
				ServiceTimeMs: 5, E2ELatencyMs: e.lastLatency,
				DeliveryRatio: e.lastDelivery, SLAViolation: violated,
			})
		}
		for _, g := range e.gateways {
			l := e.sched.At(elapsed, g.ID)
			_ = tw.Write(telemetry.Sample{
				Stamp: st, NodeID: g.ID, NodeType: "gateway",
				LossRatio: l.LossRatio, RTTMs: 10 + l.ExtraRTTMs, JitterMs: l.JitterMs,
				RetryRate:   float64(g.Retries),
				LinkQuality: linkQuality(300, l),
				EventRateHz: float64(byGW[g.ID]) / dtS,
			})
		}
	}
}

// StateID is the content address of a decision anchor. Branches are identified
// by what produced them, so two branches can never be silently confused.
func StateID(configHash string, seed uint64, tick int, history []string) string {
	h := sha256.New()
	fmt.Fprintf(h, "%s|%d|%d|", configHash, seed, tick)
	for _, a := range history {
		fmt.Fprintf(h, "%s;", a)
	}
	return hex.EncodeToString(h.Sum(nil))[:32]
}

func (e *Engine) view(elapsed float64) View {
	q := map[string]int{}
	load := map[string]float64{}
	edgeIDs := make([]string, 0, len(e.edges))
	for _, ed := range e.edges {
		q[ed.ID] = ed.Queue
		load[ed.ID] = float64(ed.Queue) / float64(e.cfg.QueueLimit)
		edgeIDs = append(edgeIDs, ed.ID)
	}
	gwIDs := make([]string, 0, len(e.gateways))
	var loss, rtt, retry float64
	for _, g := range e.gateways {
		gwIDs = append(gwIDs, g.ID)
		l := e.sched.At(elapsed, g.ID)
		loss += l.LossRatio
		rtt += 10 + l.ExtraRTTMs
		retry += float64(g.Retries)
	}
	sort.Strings(edgeIDs)
	sort.Strings(gwIDs)
	routes, throttles := e.table.Snapshot()
	n := float64(len(e.gateways))
	return View{
		ElapsedS: elapsed, QueueDepth: q, Load: load,
		LossRatio: loss / n, RTTMs: rtt / n, RetryRate: retry / n,
		E2ELatencyMs: e.lastLatency, DeliveryRatio: e.lastDelivery,
		Routes: routes, Throttles: throttles, Edges: edgeIDs, Gateways: gwIDs,
	}
}

func (e *Engine) control(tick int, elapsed float64, dw *telemetry.Writer) (bool, error) {
	v := e.view(elapsed)
	action, target, risk := e.ctrl.Decide(v, e.ctrlRnd)

	// mutated: did the action change runtime state? NO_OP executes and mutates
	// nothing, which is not the same as "had no effect" -- it is the correct
	// outcome for the null action and the reference every other branch is
	// compared against.
	mutated := false
	note := ""
	switch action {
	case Reroute:
		// Move the gateway to the least loaded edge OTHER than its current one.
		// Rerouting to the edge already in use is indistinguishable from no
		// action, and counting such a branch as a distinct alternative would
		// inflate the apparent agreement between actions in D0.
		cur := v.Routes[target]
		best := ""
		for _, id := range v.Edges {
			if id == cur {
				continue
			}
			if best == "" || v.QueueDepth[id] < v.QueueDepth[best] {
				best = id
			}
		}
		if best == "" {
			best = cur
		}
		if prev, err := e.table.Reroute(target, best); err == nil {
			mutated = prev != best
			note = fmt.Sprintf("%s: %s -> %s", target, prev, best)
		} else {
			note = err.Error()
		}
	case Throttle:
		if prev, err := e.table.Throttle(target, 0.6); err == nil {
			mutated = prev != 0.6
			note = fmt.Sprintf("%s: %.2f -> 0.60", target, prev)
		} else {
			note = err.Error()
		}
	case Release:
		if prev, err := e.table.Throttle(target, 1.0); err == nil {
			mutated = prev != 1.0
			note = fmt.Sprintf("%s: %.2f -> 1.00", target, prev)
		} else {
			note = err.Error()
		}
	case NoOp:
		mutated = false
	}

	e.history = append(e.history, string(action))
	if dw != nil {
		return mutated, dw.Write(telemetry.Decision{
			Stamp:      e.clk.Stamp(),
			DecisionID: fmt.Sprintf("%s-t%06d", e.cfg.ExperimentID, tick),
			StateID:    StateID(e.cfg.Hash(), e.cfg.MasterSeed, tick, e.history),
			Controller: e.ctrl.Name(), Action: string(action), Target: target,
			Executed: true, StateMutated: mutated, ObservedRisk: risk, Note: note,
		})
	}
	return mutated, nil
}

// ---------------------------------------------------------------------------
// Replay support
// ---------------------------------------------------------------------------

// forced replays the prefix with the base controller and then, at the anchor
// tick, executes exactly one prescribed action and nothing further. Holding the
// controller silent after the anchor is what isolates the effect of the single
// intervention: any later difference between branches is a consequence of that
// action, not of a controller reacting differently to it.
type forced struct {
	base   Controller
	anchor int
	action Action
	target string
	tick   int
}

func (f *forced) Name() string { return "replay_forced" }

func (f *forced) Decide(v View, r *rand.Rand) (Action, string, float64) {
	t := f.tick
	f.tick++
	switch {
	case t < f.anchor:
		return f.base.Decide(v, r) // identical prefix
	case t == f.anchor:
		target := f.target
		if target == "" && len(v.Gateways) > 0 {
			// Pick a target on which the action can actually take effect.
			// Throttling a gateway the prefix already throttled produces a
			// branch identical to NO_OP, which would be counted as a distinct
			// alternative while carrying no information -- M2 found exactly
			// that, with every THROTTLE branch reporting applied=false.
			target = v.Gateways[0]
			if f.action == Throttle {
				best, bestF := "", -1.0
				for _, g := range v.Gateways {
					if v.Throttles[g] > bestF {
						best, bestF = g, v.Throttles[g]
					}
				}
				if best != "" {
					target = best
				}
			}
		}
		return f.action, target, 0
	default:
		return NoOp, "", 0 // silent afterwards
	}
}

// BranchResult carries what a replayed branch actually did.
type BranchResult struct {
	// Executed: the anchor action was dispatched.
	// StateMutated: it actually changed runtime state.
	// The two differ, and conflating them is how a THROTTLE branch identical to
	// NO_OP gets counted as a distinct alternative -- which would report high
	// agreement between actions and a small dispersion band, both wrong in the
	// flattering direction. For any non-NO_OP action, StateMutated false means
	// the branch carries no information and must be excluded, not averaged in.
	Executed             bool
	StateMutated         bool
	QueueFinal, QueueMax int
	Retries, Delivered   int64
	Latencies            []float64
	Failed               bool
	Routes, Throttles    string
}

// RunBranch reconstructs the run and executes `action` at the anchor decision,
// then observes for `horizonTicks` telemetry ticks.
//
// Note what is NOT here: no snapshot is restored. The prefix is re-executed
// from the seed and configuration, which is the only reconstruction this system
// can honestly claim.
func RunBranch(cfg config.Config, base Controller, anchorDecision int,
	action Action, target string, horizonTicks int) (BranchResult, error) {
	ctrl := &forced{base: base, anchor: anchorDecision, action: action, target: target}
	e, err := New(cfg, ctrl)
	if err != nil {
		return BranchResult{}, err
	}

	ctrlEvery := cfg.Timing.TickMs / cfg.Timing.TelemetryMs
	warmTicks := cfg.Timing.WarmupS * 1000 / cfg.Timing.TelemetryMs
	anchorTick := warmTicks + anchorDecision*ctrlEvery
	stop := anchorTick + horizonTicks
	dtS := float64(cfg.Timing.TelemetryMs) / 1000

	netRnd := e.streams.Get(rng.Network, 0)
	svcRnd := e.streams.Get(rng.Service, 0)

	var res BranchResult
	// SLA failure must be attributed to the branch horizon, not to whatever the
	// shared prefix already accumulated -- otherwise every branch inherits the
	// prefix's violations and the column is constant.
	violAtAnchor := int64(-1)
	for tick := 0; tick < stop; tick++ {
		elapsed := float64(tick) * dtS
		warm := float64(cfg.Timing.WarmupS)
		e.measuring = elapsed >= warm
		e.step(tick, elapsed, dtS, netRnd, svcRnd, nil)
		if ctrlEvery > 0 && tick%ctrlEvery == 0 && tick >= warmTicks {
			mutated, err := e.control(tick, elapsed, nil)
			if err != nil {
				return res, err
			}
			if tick == anchorTick {
				res.Executed = true
				res.StateMutated = mutated
			}
		}
		if tick == anchorTick {
			violAtAnchor = e.violations
		}
		if tick >= anchorTick {
			res.Latencies = append(res.Latencies, e.lastLatency)
			q := 0
			for _, ed := range e.edges {
				q += ed.Queue
			}
			if q > res.QueueMax {
				res.QueueMax = q
			}
			res.QueueFinal = q
			if violAtAnchor >= 0 && e.violations > violAtAnchor {
				res.Failed = true
			}
		}
		e.clk.Advance()
	}
	res.Retries = e.retried
	res.Delivered = e.delivered
	routes, throttles := e.table.Snapshot()
	res.Routes = fmt.Sprint(routes)
	res.Throttles = fmt.Sprint(throttles)
	return res, nil
}

// Percentile returns the p-th percentile by nearest rank.
func Percentile(xs []float64, p float64) float64 {
	if len(xs) == 0 {
		return 0
	}
	s := append([]float64(nil), xs...)
	sort.Float64s(s)
	i := int(math.Ceil(p/100*float64(len(s)))) - 1
	if i < 0 {
		i = 0
	}
	if i >= len(s) {
		i = len(s) - 1
	}
	return s[i]
}
