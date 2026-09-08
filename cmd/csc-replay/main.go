// Command csc-replay is M2: reconstruct a run prefix and execute every
// candidate action from the same anchor.
//
// It answers one question and refuses to answer any other: do the branches
// actually differ, and do they differ in system state rather than in a label?
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"

	"github.com/TODO-OWNER/csc-iot/internal/config"
	"github.com/TODO-OWNER/csc-iot/internal/control"
	"github.com/TODO-OWNER/csc-iot/internal/faults"
	"github.com/TODO-OWNER/csc-iot/internal/replay"
	"github.com/TODO-OWNER/csc-iot/internal/sim"
)

var actions = []sim.Action{sim.NoOp, sim.Reroute, sim.Throttle}

func main() {
	var (
		seed       = flag.Uint64("seed", 42, "master seed")
		scenarioID = flag.String("scenario", "F1", "scenario id")
		devices    = flag.Int("devices", 100, "device count")
		measureS   = flag.Int("measure-s", 60, "measurement seconds")
		anchors    = flag.String("anchors", "10,20,30,40,50,60,70,80,90,100", "decision indices")
		reps       = flag.Int("reps", 1, "repetitions per branch")
		horizon    = flag.Int("horizon", 40, "telemetry ticks observed after the anchor")
		out        = flag.String("out", "data/raw/replay", "output directory")
	)
	flag.Parse()

	sc, ok := faults.ByID(*scenarioID, float64(*measureS)*0.8)
	if !ok {
		log.Fatalf("unknown scenario %q", *scenarioID)
	}
	base := control.NewThreshold()
	cfg := config.Smoke(*seed, sc, base.Name())
	cfg.Topology.Devices = *devices
	cfg.Timing.MeasureS = *measureS

	var anchorList []int
	for _, s := range splitCSV(*anchors) {
		var v int
		if _, err := fmt.Sscanf(s, "%d", &v); err != nil {
			log.Fatalf("bad anchor %q", s)
		}
		anchorList = append(anchorList, v)
	}

	if err := os.MkdirAll(*out, 0o755); err != nil {
		log.Fatal(err)
	}
	bf, err := os.Create(filepath.Join(*out, "branches.jsonl"))
	if err != nil {
		log.Fatal(err)
	}
	defer bf.Close()
	af, err := os.Create(filepath.Join(*out, "anchors.jsonl"))
	if err != nil {
		log.Fatal(err)
	}
	defer af.Close()
	benc, aenc := json.NewEncoder(bf), json.NewEncoder(af)

	fmt.Printf("%-7s %-9s %-8s %7s %7s %9s %9s %7s  %s\n",
		"anchor", "action", "mutated", "qfinal", "qmax", "p50 ms", "p99 ms", "retries", "sla")
	diverged := 0
	inertBranches := 0

	for _, a := range anchorList {
		anchor := replay.NewAnchor(cfg, a, nil)
		if err := aenc.Encode(anchor); err != nil {
			log.Fatal(err)
		}
		var p99s []float64
		for _, act := range actions {
			for rep := 0; rep < *reps; rep++ {
				// A fresh controller per branch: hysteresis state must not leak
				// from one branch into the next, or the prefixes differ.
				r, err := sim.RunBranch(cfg, control.NewThreshold(), a, act, "", *horizon)
				if err != nil {
					log.Fatal(err)
				}
				br := replay.Branch{
					Executed: r.Executed, StateMutated: r.StateMutated,
					BranchID: replay.BranchID(anchor.StateID, string(act), rep),
					StateID:  anchor.StateID, Action: string(act), Repetition: rep,
					QueueFinal: r.QueueFinal, QueueMax: r.QueueMax,
					Retries: r.Retries, Delivered: r.Delivered,
					P50Ms:  sim.Percentile(r.Latencies, 50),
					P95Ms:  sim.Percentile(r.Latencies, 95),
					P99Ms:  sim.Percentile(r.Latencies, 99),
					Failed: r.Failed, Routes: r.Routes, Throttles: r.Throttles,
				}
				if err := benc.Encode(br); err != nil {
					log.Fatal(err)
				}
				if act != sim.NoOp && !r.StateMutated {
					inertBranches++
				}
				if rep == 0 {
					p99s = append(p99s, br.P99Ms)
					fmt.Printf("%-7d %-9s %-8v %7d %7d %9.1f %9.1f %7d  %v\n",
						a, act, r.StateMutated, br.QueueFinal, br.QueueMax, br.P50Ms, br.P99Ms,
						br.Retries, br.Failed)
				}
			}
		}
		if spread(p99s) > 1e-9 {
			diverged++
		}
	}
	// "Divergence", not "distinguishability": the latter is a statement relative
	// to the dispersion band eta_J, which does not exist until D0 has been run
	// on the distributed substrate.
	fmt.Printf("\nanchors with action-dependent branch divergence: %d/%d\n",
		diverged, len(anchorList))
	fmt.Printf("inert non-NO_OP branches (dispatched but state unchanged): %d\n", inertBranches)
	if diverged == 0 {
		log.Fatal("M2 FAILED: every branch produced identical outcomes. " +
			"The actions are not reaching system state; fix that before D0.")
	}
	if inertBranches > 0 {
		log.Fatalf("M2 FAILED: %d non-NO_OP branches changed no runtime state. "+
			"Such a branch is a relabelled NO_OP and would inflate apparent "+
			"agreement between actions.", inertBranches)
	}
}

func spread(xs []float64) float64 {
	if len(xs) == 0 {
		return 0
	}
	lo, hi := xs[0], xs[0]
	for _, x := range xs {
		if x < lo {
			lo = x
		}
		if x > hi {
			hi = x
		}
	}
	return hi - lo
}

func splitCSV(s string) []string {
	var out []string
	cur := ""
	for _, c := range s {
		if c == ',' {
			out = append(out, cur)
			cur = ""
			continue
		}
		cur += string(c)
	}
	if cur != "" {
		out = append(out, cur)
	}
	return out
}
