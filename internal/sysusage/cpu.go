// Package sysusage reads this container's own resource accounting.
//
// Why this exists. The objective's cost term C(a) is declared over added
// latency, resource use, bandwidth and disruption, and only DISRUPTION was ever
// instrumented. The consequence was measured rather than guessed: across three
// matrices REROUTE won almost every contrast, and the calibration split reported
// C(NO_OP) = 0.000, C(REROUTE) = 0.000, C(THROTTLE) = 1.000. The objective was
// declaring rerouting free. It is not free -- it recruits a second edge that was
// previously idle -- but the component that would charge for that was reported
// as zero, so an action whose costs are the unmeasured ones wins by
// construction.
//
// A proxy was available and was rejected in favour of measuring the thing: CPU
// time as the kernel accounts it, for this container, from its own cgroup.
//
// HONESTY RULES, because a resource number that is quietly wrong is worse than
// one that is absent:
//   - cgroup v2 and v1 are both read; which one answered is reported.
//   - an unreadable or absent cgroup returns ok=false, and the node reports an
//     explicit absence flag. Nothing substitutes a zero.
//   - the figure is CPU time of the whole container, not of one goroutine, and
//     it therefore includes the runtime and the bus client. That is the honest
//     unit: the operator pays for the container.
package sysusage

import (
	"os"
	"strconv"
	"strings"
)

// CPUSource names where a reading came from, for the manifest.
type CPUSource string

const (
	CPUSourceCgroupV2 CPUSource = "cgroup_v2_cpu_stat"
	CPUSourceCgroupV1 CPUSource = "cgroup_v1_cpuacct"
	CPUSourceNone     CPUSource = "unavailable"
)

// CPUMicroseconds returns cumulative CPU time charged to this container.
//
// The second return value is the source; the third is false when no accounting
// could be read, in which case the first value is meaningless and must not be
// used as a zero.
func CPUMicroseconds() (uint64, CPUSource, bool) {
	// cgroup v2: a cpu.stat whose usage_usec line is already microseconds.
	if b, err := os.ReadFile("/sys/fs/cgroup/cpu.stat"); err == nil {
		for _, line := range strings.Split(string(b), "\n") {
			f := strings.Fields(line)
			if len(f) == 2 && f[0] == "usage_usec" {
				if v, err := strconv.ParseUint(f[1], 10, 64); err == nil {
					return v, CPUSourceCgroupV2, true
				}
			}
		}
	}
	// cgroup v1: cpuacct.usage in NANOseconds. The unit differs from v2 and
	// mixing them would be a silent factor of a thousand.
	if b, err := os.ReadFile("/sys/fs/cgroup/cpuacct/cpuacct.usage"); err == nil {
		if v, err := strconv.ParseUint(strings.TrimSpace(string(b)), 10, 64); err == nil {
			return v / 1000, CPUSourceCgroupV1, true
		}
	}
	return 0, CPUSourceNone, false
}
