// Command csc-sim runs one Phase A experiment and writes telemetry, decisions
// and a manifest.
//
// No machine learning is involved and none may be added before the determinism
// and replay gates in BACKLOG.md are passed.
package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/TODO-OWNER/csc-iot/internal/config"
	"github.com/TODO-OWNER/csc-iot/internal/control"
	"github.com/TODO-OWNER/csc-iot/internal/experiment"
	"github.com/TODO-OWNER/csc-iot/internal/faults"
	"github.com/TODO-OWNER/csc-iot/internal/sim"
	"github.com/TODO-OWNER/csc-iot/internal/telemetry"
)

func gitCommit() string {
	out, err := exec.Command("git", "rev-parse", "--short", "HEAD").Output()
	if err != nil {
		return "nogit"
	}
	return strings.TrimSpace(string(out))
}

func main() {
	var (
		seed       = flag.Uint64("seed", 42, "master seed")
		scenarioID = flag.String("scenario", "F1", "scenario id (F1|F2)")
		devices    = flag.Int("devices", 100, "virtual device count")
		measureS   = flag.Int("measure-s", 60, "measurement seconds")
		outDir     = flag.String("out", "data/raw", "raw output directory")
		manDir     = flag.String("manifests", "experiments/manifests", "manifest directory")
		impairment = flag.String("impairment", "application_layer", "kernel_netem|application_layer")
	)
	flag.Parse()

	scenario, ok := faults.ByID(*scenarioID, float64(*measureS)*0.8)
	if !ok {
		log.Fatalf("unknown scenario %q (Phase A implements F1 and F2)", *scenarioID)
	}
	ctrl := control.NewThreshold()
	cfg := config.Smoke(*seed, scenario, ctrl.Name())
	cfg.Topology.Devices = *devices
	cfg.Timing.MeasureS = *measureS
	cfg.ImpairmentMode = *impairment
	if err := cfg.Validate(); err != nil {
		log.Fatalf("invalid config: %v", err)
	}

	runDir := filepath.Join(*outDir, cfg.ExperimentID)
	tw, err := telemetry.NewWriter(runDir, "telemetry.jsonl")
	if err != nil {
		log.Fatalf("telemetry: %v", err)
	}
	dw, err := telemetry.NewWriter(runDir, "decisions.jsonl")
	if err != nil {
		log.Fatalf("decisions: %v", err)
	}

	man := experiment.New(cfg.ExperimentID, cfg.MasterSeed, cfg.Scenario.ID, ctrl.Name(),
		cfg.Topology.Devices, cfg.Hash(), gitCommit(), cfg.ImpairmentMode)

	eng, err := sim.New(cfg, ctrl)
	if err != nil {
		log.Fatalf("engine: %v", err)
	}
	counters, err := eng.Run(tw, dw)
	if err != nil {
		man.Finish("failed")
		_ = man.Write(*manDir)
		log.Fatalf("run: %v", err)
	}
	if err := tw.Close(); err != nil {
		log.Fatalf("close telemetry: %v", err)
	}
	if err := dw.Close(); err != nil {
		log.Fatalf("close decisions: %v", err)
	}

	for k, v := range counters {
		man.Count(k, v)
	}
	telPath := filepath.Join(runDir, "telemetry.jsonl")
	if sum, err := experiment.FileSHA256(telPath); err == nil {
		man.TelemetrySHA = sum
	}
	// The fingerprint that must be stable across runs at the same seed.
	if sum, err := experiment.DeterminismDigest(telPath, "wall_nanos"); err == nil {
		man.DeterminismSHA = sum
	} else {
		log.Fatalf("determinism digest: %v", err)
	}
	man.Finish("ok")
	if err := man.Write(*manDir); err != nil {
		log.Fatalf("manifest: %v", err)
	}

	fmt.Fprintf(os.Stdout,
		"run %s  scenario=%s devices=%d impairment=%s\n"+
			"  events sent=%d delivered=%d retries=%d sla_violation_ticks=%d\n"+
			"  determinism sha256=%s\n"+
			"  manifest %s\n",
		cfg.ExperimentID, cfg.Scenario.ID, cfg.Topology.Devices, cfg.ImpairmentMode,
		counters["events_sent"], counters["events_delivered"], counters["retries"],
		counters["sla_violation_ticks"], man.DeterminismSHA[:16],
		filepath.Join(*manDir, cfg.ExperimentID+".json"))
}
