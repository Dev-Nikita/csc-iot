package bus

import "encoding/json"

// One envelope encoding shared by every adapter, so a message means the same
// thing whichever transport carried it and a trace recorded on one stack can be
// read against another.
func encodeEnvelope(e Envelope) ([]byte, error) { return json.Marshal(e) }

func decodeEnvelope(b []byte) (Envelope, error) {
	var e Envelope
	err := json.Unmarshal(b, &e)
	return e, err
}
