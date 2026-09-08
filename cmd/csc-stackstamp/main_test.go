package main

import "testing"

func TestStableNetemConfigIgnoresRuntimeHandleAndInterface(t *testing.T) {
	a := "device-sim:eth0 qdisc netem 8001: root refcnt 5 limit 1000 delay 20ms 5ms loss 5% seed 424242"
	b := "device-sim:eth1 qdisc netem 8017: root refcnt 11 limit 1000 delay 20ms 5ms loss 5% seed 424242"
	if stableNetemConfig(a) != stableNetemConfig(b) {
		t.Fatal("runtime qdisc handle/interface changed semantic stack identity")
	}
}

func TestStableNetemConfigKeepsTargetAndParameters(t *testing.T) {
	base := "device-sim:eth0 qdisc netem 8001: root refcnt 5 limit 1000 delay 20ms 5ms loss 5% seed 424242"
	changedSeed := "device-sim:eth0 qdisc netem 8001: root refcnt 5 limit 1000 delay 20ms 5ms loss 5% seed 7"
	wrongDirection := "gateway00:eth0 qdisc netem 8001: root refcnt 5 limit 1000 delay 20ms 5ms loss 5% seed 424242"
	if stableNetemConfig(base) == stableNetemConfig(changedSeed) {
		t.Fatal("netem seed must be part of stack identity")
	}
	if stableNetemConfig(base) == stableNetemConfig(wrongDirection) {
		t.Fatal("netem target/direction must be part of stack identity")
	}
}
