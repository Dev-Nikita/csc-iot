// Package experiment writes the per-run manifest.
//
// Every reported number must be traceable to a manifest. A run without one is
// not a result; the analysis pipeline refuses to read it.
package experiment

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"time"
)

type Manifest struct {
	ExperimentID   string            `json:"experiment_id"`
	MasterSeed     uint64            `json:"master_seed"`
	Scenario       string            `json:"scenario"`
	Controller     string            `json:"controller"`
	DeviceCount    int               `json:"device_count"`
	ConfigSHA256   string            `json:"config_sha256"`
	GitCommit      string            `json:"git_commit"`
	StartedAt      string            `json:"started_at"`
	FinishedAt     string            `json:"finished_at"`
	ImpairmentMode string            `json:"impairment_mode"`
	Software       map[string]string `json:"software_versions"`
	Host           map[string]string `json:"host"`
	Counters       map[string]int64  `json:"counters"`
	// Raw file hash: differs between runs at the same seed, because telemetry
	// carries wall-clock time. Useful for integrity, useless for reproducibility.
	TelemetrySHA string `json:"telemetry_sha256"`
	// Wall-clock-independent digest: two runs at the same seed MUST match here.
	// This is the reproducibility fingerprint a reviewer should check.
	DeterminismSHA string `json:"determinism_sha256"`
	ExitStatus     string `json:"exit_status"`
}

func New(id string, seed uint64, scenario, controller string, devices int,
	configHash, commit, impairment string) *Manifest {
	return &Manifest{
		ExperimentID: id, MasterSeed: seed, Scenario: scenario, Controller: controller,
		DeviceCount: devices, ConfigSHA256: configHash, GitCommit: commit,
		StartedAt: time.Now().UTC().Format(time.RFC3339), ImpairmentMode: impairment,
		Software: map[string]string{"go": runtime.Version()},
		Host:     map[string]string{"os": runtime.GOOS, "arch": runtime.GOARCH, "cpus": fmt.Sprint(runtime.NumCPU())},
		Counters: map[string]int64{},
	}
}

func (m *Manifest) Count(k string, n int64) { m.Counters[k] += n }

// FileSHA256 fingerprints a telemetry file. Two runs at the same seed must
// produce the same digest; that check is what makes replay credible, and it is
// asserted in the determinism test rather than assumed.
func FileSHA256(path string) (string, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:]), nil
}

func (m *Manifest) Finish(status string) {
	m.FinishedAt = time.Now().UTC().Format(time.RFC3339)
	m.ExitStatus = status
}

func (m *Manifest) Write(dir string) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	// stable key order for diffable manifests
	keys := make([]string, 0, len(m.Counters))
	for k := range m.Counters {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	b, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(dir, m.ExperimentID+".json"), append(b, '\n'), 0o644)
}

// DeterminismDigest fingerprints a JSONL file with the named keys removed at
// every nesting level.
//
// It exists because one field in every record -- the wall clock -- is expected
// to differ between two runs of the same seed, while everything else must not.
// Hashing the file verbatim would therefore report a failure on every run and
// train us to ignore the check, which is worse than having no check.
func DeterminismDigest(path string, ignore ...string) (string, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	drop := map[string]bool{}
	for _, k := range ignore {
		drop[k] = true
	}
	h := sha256.New()
	for _, line := range splitLines(b) {
		if len(line) == 0 {
			continue
		}
		var v any
		if err := json.Unmarshal(line, &v); err != nil {
			return "", fmt.Errorf("%s: %w", path, err)
		}
		canonical, err := json.Marshal(strip(v, drop))
		if err != nil {
			return "", err
		}
		h.Write(canonical)
		h.Write([]byte{'\n'})
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func splitLines(b []byte) [][]byte {
	var out [][]byte
	start := 0
	for i, c := range b {
		if c == '\n' {
			out = append(out, b[start:i])
			start = i + 1
		}
	}
	if start < len(b) {
		out = append(out, b[start:])
	}
	return out
}

func strip(v any, drop map[string]bool) any {
	switch t := v.(type) {
	case map[string]any:
		out := make(map[string]any, len(t))
		for k, val := range t {
			if drop[k] {
				continue
			}
			out[k] = strip(val, drop)
		}
		return out
	case []any:
		for i := range t {
			t[i] = strip(t[i], drop)
		}
		return t
	default:
		return v
	}
}
