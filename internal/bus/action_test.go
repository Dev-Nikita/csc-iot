package bus

import (
	"encoding/json"
	"testing"
)

func TestActionProtocolCarriesRunAndActionIdentity(t *testing.T) {
	want := ActionCommand{RunID: "run-1", ActionID: "act-1", Target: "gw00", Action: "REROUTE", Edge: "edge01"}
	body, err := json.Marshal(want)
	if err != nil {
		t.Fatal(err)
	}
	var got ActionCommand
	if err := json.Unmarshal(body, &got); err != nil {
		t.Fatal(err)
	}
	if got != want {
		t.Fatalf("action identity changed over the wire: got %+v want %+v", got, want)
	}
}
