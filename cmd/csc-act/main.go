// Command csc-act publishes one control-plane action.
//
// It stands in for the controller's action path until the decision loop is
// wired in M2'. Its real job right now is to let the topology smoke test prove
// that REROUTE moves traffic, rather than updating a map nothing reads.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"log"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
)

func main() {
	busAddr := flag.String("bus", "127.0.0.1:4300", "message bus address")
	target := flag.String("target", "gw00", "gateway to act on")
	action := flag.String("action", "REROUTE", "action")
	edge := flag.String("edge", "edge01", "destination edge for REROUTE")
	flag.Parse()

	b, err := bus.DialTCP(*busAddr, 2*time.Second)
	if err != nil {
		log.Fatalf("bus: %v", err)
	}
	defer b.Close()
	actionID := "manual-" + time.Now().UTC().Format("20060102T150405.000000000")
	payload, _ := json.Marshal(bus.ActionCommand{
		RunID: "manual", ActionID: actionID, Target: *target,
		Action: *action, Edge: *edge,
	})
	if err := b.Publish(context.Background(), bus.SubjectControllerActions, bus.Envelope{
		ExperimentID: "manual", ProducerID: "csc-act", EventID: actionID, Payload: payload,
	}); err != nil {
		log.Fatalf("publish: %v", err)
	}
	time.Sleep(200 * time.Millisecond) // let the frame leave before the socket closes
	log.Printf("published %s %s -> %s", *action, *target, *edge)
}
