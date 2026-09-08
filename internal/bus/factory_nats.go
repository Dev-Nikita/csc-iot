//go:build nats

package bus

func init() { Register("nats", DialNATS) }
