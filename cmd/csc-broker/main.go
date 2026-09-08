// Command csc-broker runs the development message bus.
//
// It is the stdlib TCP broker, not NATS, and every manifest it takes part in
// records that. Swapping in the NATS adapter changes the runtime stack id and
// invalidates any dispersion band measured against this one.
package main

import (
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/TODO-OWNER/csc-iot/internal/bus"
)

func main() {
	addr := flag.String("addr", ":4300", "listen address")
	flag.Parse()

	b, err := bus.StartBroker(*addr)
	if err != nil {
		log.Fatalf("broker: %v", err)
	}
	log.Printf("csc-broker listening on %s (transport=stdlib-tcp, NOT nats)", b.Addr())

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig
	log.Print("csc-broker shutting down")
	_ = b.Close()
}
