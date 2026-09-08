package routing

import "testing"

func TestRerouteChangesRealState(t *testing.T) {
	tb := NewTable([]string{"gw00", "gw01"}, []string{"edge00", "edge01", "edge02"})
	before := tb.EdgeFor("gw00")
	prev, err := tb.Reroute("gw00", "edge02")
	if err != nil {
		t.Fatal(err)
	}
	if prev != before {
		t.Fatalf("previous edge misreported: %s != %s", prev, before)
	}
	if tb.EdgeFor("gw00") != "edge02" {
		t.Fatal("reroute did not take effect")
	}
}

func TestRerouteRejectsUnknowns(t *testing.T) {
	tb := NewTable([]string{"gw00"}, []string{"edge00"})
	if _, err := tb.Reroute("nope", "edge00"); err == nil {
		t.Fatal("unknown gateway accepted")
	}
	if _, err := tb.Reroute("gw00", "nope"); err == nil {
		t.Fatal("unknown edge accepted")
	}
}

func TestThrottleBounds(t *testing.T) {
	tb := NewTable([]string{"gw00"}, []string{"edge00"})
	for _, bad := range []float64{0, -0.5, 1.5} {
		if _, err := tb.Throttle("gw00", bad); err == nil {
			t.Fatalf("accepted out-of-range throttle %v", bad)
		}
	}
	if _, err := tb.Throttle("gw00", 0.6); err != nil {
		t.Fatal(err)
	}
	if tb.ThrottleFor("gw00") != 0.6 {
		t.Fatal("throttle did not take effect")
	}
}
