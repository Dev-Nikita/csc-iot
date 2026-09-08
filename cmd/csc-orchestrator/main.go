// Command csc-orchestrator drives epochs across the live topology and collects
// the structural fingerprint at an anchor.
//
// This is the first step of M2' and it asks one question, deliberately narrow:
// do two runs of the distributed system, started from the same prefix
// specification, reach the same structural state at the same anchor?
//
// If they do, replay over real processes is possible and the branch machinery
// has something to stand on. If they do not, the honest outcome is to see
// exactly which field diverges, at what magnitude, before anything is built on
// top of it. That is worth more than a working branch runner over states that
// were never equal.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
	"github.com/TODO-OWNER/csc-iot/internal/epoch"
	"github.com/TODO-OWNER/csc-iot/internal/fingerprint"
	"github.com/TODO-OWNER/csc-iot/internal/nodestate"
)

func main() {
	var (
		busAddr  = flag.String("bus", "127.0.0.1:4222", "message bus address")
		busImpl  = flag.String("bus-impl", "nats", "transport: tcp | nats")
		nodesCSV = flag.String("nodes", "gw00,gw01,edge00,edge01,edge02,ctl", "expected participants")
		anchor   = flag.Int64("anchor", 5, "epoch at which to fingerprint")
		epochs   = flag.Int64("epochs", 8, "epochs to drive")
		period   = flag.Duration("period", 500*time.Millisecond, "wall time per epoch")
		timeout  = flag.Duration("timeout", 8*time.Second, "per-barrier timeout")
		cfgHash  = flag.String("config-hash", "m2prime", "configuration hash for the fingerprint")
		out      = flag.String("out", "", "write the anchor fingerprint here (JSON)")
		stackID  = flag.String("runtime-stack-id", "", "reportable runtime_stack_id this anchor belongs to")
		gitSHA   = flag.String("git-commit", "", "git commit of the tree that produced this anchor")
		runIDArg = flag.String("run-id", "", "run identity (default: generated)")
		action   = flag.String("action", "NO_OP", "branch action applied AT the anchor: NO_OP | THROTTLE | REROUTE")
		actTgt   = flag.String("action-target", "gw00", "gateway the action acts on")
		actEdge  = flag.String("action-edge", "edge01", "destination edge for REROUTE")
		actLimit = flag.Int64("action-limit", 50, "per-epoch admission cap for THROTTLE")
		horizon  = flag.Int64("horizon", 3, "epochs to run after the anchor before the outcome is read")
		outDir   = flag.String("out-dir", "", "branch directory: anchor.json, outcome.json and branch.json are written here")
		branchID = flag.String("branch-id", "", "identifier of this branch within the matrix")
		prodCSV  = flag.String("producers", "gw00,gw01", "nodes that must close every epoch before it can be read")
	)
	flag.Parse()

	nodes := strings.Split(*nodesCSV, ",")
	if *outDir != "" && *epochs < *anchor+*horizon {
		log.Fatalf("epochs (%d) must reach the outcome point anchor+horizon (%d)",
			*epochs, *anchor+*horizon)
	}

	runID := *runIDArg
	if runID == "" {
		runID = epoch.NewRunID()
	}
	log.Printf("run %s", runID)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	b, err := bus.Dial(*busImpl, *busAddr, 5*time.Second)
	if err != nil {
		log.Fatalf("bus: %v", err)
	}
	defer b.Close()
	d := b.Descriptor()
	log.Printf("orchestrator on %s [%s/%s]", *busAddr, d.Type, d.Version)
	actionAcks := make(chan bus.ActionAck, 16)
	if err := b.Subscribe(ctx, bus.SubjectControllerActionAcks, func(e bus.Envelope) {
		var ack bus.ActionAck
		if json.Unmarshal(e.Payload, &ack) == nil {
			select {
			case actionAcks <- ack:
			default:
			}
		}
	}); err != nil {
		log.Fatalf("action acknowledgement subscription: %v", err)
	}

	coord, err := epoch.NewCoordinator(ctx, b, runID, nodes)
	if err != nil {
		log.Fatalf("coordinator: %v", err)
	}
	wm, err := epoch.NewWatermark(ctx, b, runID, nodes)
	if err != nil {
		log.Fatalf("watermark: %v", err)
	}
	wm.ExpectProducers(strings.Split(*prodCSV, ","))
	time.Sleep(300 * time.Millisecond) // let subscriptions register

	appliedAction := "NO_OP"
	var verifiedActionAck *bus.ActionAck
	var history []string
	for k := int64(1); k <= *epochs; k++ {
		if err := coord.Declare(ctx, k); err != nil {
			log.Fatalf("epoch %d: declare: %v", k, err)
		}
		if err := coord.Await(ctx, k, *timeout); err != nil {
			// Not a warning. An anchor taken over an unsynchronised prefix is
			// the defect the barrier exists to prevent.
			log.Fatalf("epoch %d: %v", k, err)
		}
		// Quiescence is a precondition for the fingerprint, not a warning.
		//
		// Proceeding without it was measurably wrong: with the barrier alone,
		// two runs from the same specification recorded 600 and 561 events
		// consumed at the same anchor -- the gateway had published identically,
		// but the edge had not finished draining, and the fingerprint captured
		// the difference as if it were state.
		isReadPoint := k == *anchor || (*horizon > 0 && k == *anchor+*horizon)
		if err := wm.AwaitQuiescent(ctx, k, *timeout); err != nil {
			if isReadPoint {
				log.Fatalf("epoch %d: refusing to fingerprint an undrained transport: %v", k, err)
			}
			log.Printf("epoch %d: not quiescent (no anchor here): %v", k, err)
		}
		history = append(history, "NO_OP")

		if isReadPoint {
			what := "anchor"
			if k != *anchor {
				what = "outcome"
			}
			reqID := fmt.Sprintf("%s-%d-%d", what, k, time.Now().UnixNano())
			col, err := nodestate.NewCollector(ctx, b, nodes, reqID)
			if err != nil {
				log.Fatalf("collector: %v", err)
			}
			payload, _ := json.Marshal(nodestate.Request{Epoch: k, RequestID: reqID})
			if err := b.Publish(ctx, nodestate.SubjectRequest, bus.Envelope{
				LogicalTick: k, ProducerID: "orchestrator", EventID: reqID, Payload: payload,
			}); err != nil {
				log.Fatalf("fingerprint request: %v", err)
			}
			select {
			case <-col.Done():
			case <-time.After(*timeout):
				log.Fatalf("anchor %d: no fingerprint from %v", k, col.Missing())
			}

			fp := col.Combine(k, *cfgHash, fmt.Sprintf("epoch=%d", k), history)

			// The quiescence check and the snapshot must be the same moment.
			// Separating them is how an anchor came to record
			// drained:edge00:gw00 = 1866 against end:gw00 = 2000: the check had
			// passed, and the numbers written were not the numbers checked.
			q, err := wm.TransportQuiescenceFingerprintVerified(k)
			if err != nil {
				log.Fatalf("anchor %d: refusing to write an anchor over an undrained transport: %v", k, err)
			}
			fp.TransportQuiescence = q
			hash := fp.Hash()
			log.Printf("%s %d: structural fingerprint %s", what, k, hash[:32])
			for name, q := range fp.Queues {
				log.Printf("   queue %-18s len=%d content=%s", name, q.Length, q.ContentHash[:8])
			}
			for name, v := range fp.SeqPositions {
				log.Printf("   seq   %-18s %d", name, v)
			}
			for name, v := range fp.ProcessedCounts {
				log.Printf("   proc  %-18s %d", name, v)
			}
			target := *out
			if *outDir != "" {
				target = filepath.Join(*outDir, what+".json")
			}
			if target != "" {
				body, _ := json.MarshalIndent(struct {
					Hash           string                 `json:"hash"`
					RunID          string                 `json:"run_id"`
					RuntimeStackID string                 `json:"runtime_stack_id"`
					GitCommit      string                 `json:"git_commit"`
					ConfigHash     string                 `json:"config_hash"`
					State          fingerprint.Structural `json:"state"`
					Observed       map[string]float64     `json:"observed,omitempty"`
					Epoch          int64                  `json:"epoch"`
					Kind           string                 `json:"kind"`
					BranchID       string                 `json:"branch_id"`
					Action         string                 `json:"action"`
				}{hash, runID, *stackID, *gitSHA, *cfgHash, fp, col.Observed(), k, what, *branchID, appliedAction}, "", "  ")

				// Append-only. An anchor overwritten by the next run is not
				// evidence: the file that was audited and the file on disk stop
				// being the same object, silently.
				if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
					log.Fatalf("write: %v", err)
				}
				f, err := os.OpenFile(target, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o444)
				if err != nil {
					log.Fatalf("write: %v (anchors are never overwritten; choose a new path)", err)
				}
				if _, err := f.Write(append(body, '\n')); err != nil {
					log.Fatalf("write: %v", err)
				}
				if err := f.Close(); err != nil {
					log.Fatalf("write: %v", err)
				}
				log.Printf("wrote %s", target)
			}
			// The action is applied AFTER the anchor state has been recorded and
			// BEFORE the next epoch, so the branch differs from its siblings in
			// the action and in nothing else that the anchor did not already fix.
			if k == *anchor && *action != "NO_OP" {
				actionID := fmt.Sprintf("%s-act-%d", runID, k)
				command := bus.ActionCommand{
					RunID: runID, ActionID: actionID, Target: *actTgt,
					Action: *action, Edge: *actEdge, Limit: *actLimit,
				}
				payload, _ := json.Marshal(command)
				if err := b.Publish(ctx, bus.SubjectControllerActions, bus.Envelope{
					ExperimentID: runID, LogicalTick: k, ProducerID: "orchestrator",
					EventID: actionID, Payload: payload,
				}); err != nil {
					log.Fatalf("anchor %d: action %s not published: %v", k, *action, err)
				}
				deadline := time.After(*timeout)
				for verifiedActionAck == nil {
					select {
					case ack := <-actionAcks:
						if ack.RunID != runID || ack.ActionID != actionID || ack.Target != *actTgt {
							continue
						}
						if !ack.Applied || ack.Action != *action {
							log.Fatalf("anchor %d: action %s rejected by %s: %s", k, *action, *actTgt, ack.Detail)
						}
						copy := ack
						verifiedActionAck = &copy
					case <-deadline:
						log.Fatalf("anchor %d: action %s was published but not acknowledged by %s", k, *action, *actTgt)
					}
				}
				appliedAction = *action
				history[len(history)-1] = *action
				log.Printf("anchor %d: verified %s on %s (%s)", k, *action, *actTgt, verifiedActionAck.Detail)
			}
		}
		time.Sleep(*period)
	}
	if *outDir != "" {
		body, _ := json.MarshalIndent(struct {
			RunID          string         `json:"run_id"`
			BranchID       string         `json:"branch_id"`
			RuntimeStackID string         `json:"runtime_stack_id"`
			Action         string         `json:"action"`
			ActionAck      *bus.ActionAck `json:"action_ack,omitempty"`
		}{runID, *branchID, *stackID, appliedAction, verifiedActionAck}, "", "  ")
		target := filepath.Join(*outDir, "branch.json")
		f, err := os.OpenFile(target, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o444)
		if err != nil {
			log.Fatalf("write: %v", err)
		}
		if _, err := f.Write(append(body, '\n')); err != nil {
			log.Fatalf("write: %v", err)
		}
		if err := f.Close(); err != nil {
			log.Fatalf("write: %v", err)
		}
	}
	log.Printf("drove %d epochs, anchor at %d, action %s", *epochs, *anchor, appliedAction)
}
