// Command csc-stackstamp records the runtime stack a measurement belongs to.
//
// eta_J is shaped by transport, buffering, scheduling and kernel behaviour, so a
// dispersion band measured on one stack does not transfer to another. This tool
// writes the identity of the stack that is actually running, and it does not
// decide whether that stack is reportable -- check_reportable_stack.py does,
// from the file written here. Keeping the two apart matters: a tool that both
// gathered the facts and blessed them could be talked into blessing anything.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"time"
)

type stamp struct {
	ReportableStackValidated bool              `json:"reportable_stack_validated"`
	RuntimeStackID           string            `json:"runtime_stack_id"`
	GoVersion                string            `json:"go_version"`
	Kernel                   string            `json:"kernel"`
	BusType                  string            `json:"bus_type"`
	BusVersion               string            `json:"bus_version"`
	TransportConfigHash      string            `json:"transport_config_hash"`
	RPCType                  string            `json:"rpc_type"`
	ImpairmentMode           string            `json:"impairment_mode"`
	NetemConfig              string            `json:"netem_config"`
	ProcessTopology          string            `json:"process_topology"`
	ContainerImages          map[string]string `json:"container_images"`
	StampedAt                string            `json:"stamped_at"`
	Blockers                 []string          `json:"blockers"`
	Notes                    []string          `json:"notes"`
}

func run(name string, args ...string) (string, error) {
	out, err := exec.Command(name, args...).Output()
	return strings.TrimSpace(string(out)), err
}

// containerKernel asks a running container, not the host. On macOS the host is
// Darwin while the containers run under a LinuxKit VM, and it is the latter that
// shapes scheduling and therefore the dispersion band.
func containerKernel(service string) string {
	if cid, err := run("docker", "compose", "ps", "-q", service); err == nil && cid != "" {
		if out, err := run("docker", "exec", cid, "uname", "-sr"); err == nil && out != "" {
			return out
		}
	}
	if out, err := run("docker", "run", "--rm", "alpine:3.20", "uname", "-sr"); err == nil {
		return out
	}
	return "unknown"
}

func containerGoVersion(service string) string {
	cid, err := run("docker", "compose", "ps", "-q", service)
	if err == nil && cid != "" {
		if out, err := run("docker", "exec", cid, "/usr/local/bin/app", "-version"); err == nil && out != "" {
			return out
		}
	}
	return runtime.Version() + " (stackstamp host fallback)"
}

func composeImages() map[string]string {
	imgs := map[string]string{}
	out, err := run("docker", "compose", "ps", "--format", "{{.Service}} {{.Image}}")
	if err != nil {
		return imgs
	}
	for _, line := range strings.Split(out, "\n") {
		f := strings.Fields(line)
		if len(f) != 2 {
			continue
		}
		digest, err := run("docker", "inspect", "-f", "{{index .RepoDigests 0}}", f[1])
		if err != nil || digest == "" {
			// Locally built images have no repo digest; the image ID still
			// identifies the bits that ran.
			digest, _ = run("docker", "inspect", "-f", "{{.Id}}", f[1])
		}
		imgs[f[0]] = digest
	}
	return imgs
}

// netemOn finds an active netem qdisc anywhere in a service's container.
//
// It scans every interface rather than trusting a name. Docker assigns eth0,
// eth1 in the order networks happen to attach, and that order is not stable
// across a recreate: a stack whose ingress was eth0 before `up --build` can come
// back with ingress on eth1. Looking at a fixed name reported "no netem qdisc"
// on a correctly impaired stack -- a false negative that reads like the
// impairment failed.
//
// Which interface is the RIGHT one to impair is netem_smoke.sh's job; it checks
// that the qdisc landed on the ingress network and nowhere else. This function
// only records what is actually in force.
func netemOn(service string) (iface, qdisc string) {
	cid, err := run("docker", "compose", "ps", "-q", service)
	if err != nil || cid == "" {
		return "", ""
	}
	links, err := run("docker", "exec", cid, "sh", "-c",
		`ip -o link | awk '{split($2,a,/[@:]/); print a[1]}'`)
	if err != nil {
		return "", ""
	}
	for _, name := range strings.Fields(links) {
		if name == "lo" {
			continue
		}
		out, err := run("docker", "exec", cid, "tc", "qdisc", "show", "dev", name)
		if err != nil || !strings.Contains(out, "netem") {
			continue
		}
		return name, out
	}
	return "", ""
}

func main() {
	var (
		busType   = flag.String("bus", "", "transport actually in use (tcp|nats)")
		busVer    = flag.String("bus-version", "", "transport version")
		transHash = flag.String("transport-hash", "", "transport config hash")
		rpcType   = flag.String("rpc", "stdlib-framed-tcp", "RPC implementation in use")
		topology  = flag.String("topology", "1 broker, 2 gateways, 3 edges, 1 controller, 1 intelligence, 1 device simulator", "process topology")
		netemSvc  = flag.String("netem-service", "device-sim", "service carrying device-to-gateway egress impairment")
		_ = flag.String("netem-iface", "", "deprecated: every interface is scanned")
		out       = flag.String("out", "experiments/manifests/reportable_stack.json", "output path")
	)
	flag.Parse()

	if *busType == "" {
		fmt.Fprintln(os.Stderr,
			"-bus is required: the stamp must record the transport that actually ran,\n"+
				"not a default. Pass -bus tcp for the development substrate or -bus nats\n"+
				"once the nodes are built with -tags=nats and pointed at a NATS server.")
		os.Exit(2)
	}

	s := stamp{
		GoVersion:           containerGoVersion("gateway00"),
		Kernel:              containerKernel("gateway00"),
		BusType:             *busType,
		BusVersion:          *busVer,
		TransportConfigHash: *transHash,
		RPCType:             *rpcType,
		ProcessTopology:     *topology,
		ContainerImages:     composeImages(),
		StampedAt:           time.Now().UTC().Format(time.RFC3339),
	}

	if iface, q := netemOn(*netemSvc); q != "" {
		s.ImpairmentMode = "kernel_netem"
		s.NetemConfig = *netemSvc + ":" + iface + " " + q
	} else {
		s.ImpairmentMode = "application_layer"
	}

	// Blockers are recorded, not hidden. The checker reads them too, but a
	// person reading this file should see immediately why a stack is not
	// reportable rather than having to run another tool to find out.
	if s.BusType == "tcp" {
		s.Blockers = append(s.Blockers,
			"bus_type=tcp is the development broker; rebuild the nodes with -tags=nats and run against a NATS server")
	}
	if s.RPCType == "stdlib-framed-tcp" {
		s.Notes = append(s.Notes,
			"rpc_type=stdlib-framed-tcp is the development RPC. It does not block a "+
				"reportable run while the manuscript claims only a typed RPC boundary, "+
				"which this adapter is. If a draft ever names gRPC, this must change first.")
	}
	if s.ImpairmentMode != "kernel_netem" {
		s.Blockers = append(s.Blockers,
			"no netem qdisc found on any interface of "+*netemSvc+"; runs would be "+
				"application-layer impaired. netem_smoke.sh removes the qdisc on exit "+
				"unless KEEP=1 -- use `make netem-apply`.")
	}
	if s.Kernel == "unknown" {
		s.Blockers = append(s.Blockers, "container kernel could not be determined")
	}
	if s.TransportConfigHash == "" {
		s.Blockers = append(s.Blockers, "transport_config_hash is empty")
	}

	// The development RPC alone does not disqualify a stack: the paper claims a
	// typed RPC boundary and the framed adapter is one. The bus and the
	// impairment mode do.
	// Blockers disqualify a stack; notes do not.
	s.ReportableStackValidated = len(s.Blockers) == 0
	s.RuntimeStackID = stackID(s)

	if err := os.MkdirAll(filepath.Dir(*out), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	b, _ := json.MarshalIndent(s, "", "  ")
	if err := os.WriteFile(*out, append(b, '\n'), 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	fmt.Printf("runtime_stack_id=%s bus=%s rpc=%s impairment=%s\n",
		s.RuntimeStackID, s.BusType, s.RPCType, s.ImpairmentMode)
	for _, n := range s.Notes {
		fmt.Println("note: " + n)
	}
	if len(s.Blockers) > 0 {
		fmt.Println("blockers:")
		for _, b := range s.Blockers {
			fmt.Println("  - " + b)
		}
	}
	fmt.Printf("wrote %s (reportable=%v)\n", *out, s.ReportableStackValidated)
}

func stackID(s stamp) string {
	keys := make([]string, 0, len(s.ContainerImages))
	for k := range s.ContainerImages {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var sb strings.Builder
	fmt.Fprintf(&sb, "%s|%s|%s|%s|%s|%s|%s|%s|",
		s.GoVersion, s.Kernel, s.BusType, s.BusVersion,
		s.TransportConfigHash, s.RPCType, s.ProcessTopology, stableNetemConfig(s.NetemConfig))
	for _, k := range keys {
		fmt.Fprintf(&sb, "%s=%s;", k, s.ContainerImages[k])
	}
	return sha16(sb.String())
}

// Linux assigns qdisc handles and refcnt values at runtime. They are useful in
// the evidence manifest but are not semantic stack configuration, so they must
// not make an otherwise identical recreated branch acquire a new stack id.
func stableNetemConfig(raw string) string {
	target := raw
	if i := strings.Index(raw, ":"); i >= 0 {
		target = raw[:i]
	}
	fields := strings.Fields(raw)
	for i, field := range fields {
		if field == "limit" {
			return target + ":data-egress " + strings.Join(fields[i:], " ")
		}
	}
	return raw
}

func sha16(s string) string {
	h := sha256.Sum256([]byte(s))
	return hex.EncodeToString(h[:])[:16]
}
