// Command csc-intelligence serves the stub intelligence plane.
//
// There is no model behind it and there is not meant to be one yet. Its job is
// to make the boundary measurable before the model exists: RPC latency, the
// enforced deadline, and the fallback the controller takes when the deadline is
// missed. Scores are deterministic and obviously synthetic so that nobody reads
// meaning into them.
package main

import (
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/TODO-OWNER/csc-iot/internal/rpc"
)

func main() {
	addr := flag.String("addr", ":50051", "listen address")
	delay := flag.Duration("delay", 5*time.Millisecond, "synthetic inference delay")
	flag.Parse()

	s, err := rpc.StartStub(*addr, *delay)
	if err != nil {
		log.Fatalf("intelligence: %v", err)
	}
	log.Printf("csc-intelligence (stub) on %s delay=%v rpc_type=stdlib-framed-tcp", s.Addr(), *delay)

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig
	_ = s.Close()
}
