//go:build grpc

// NEEDS_LOCAL_VALIDATION.
//
// Excluded from the default build: google.golang.org/grpc and protobuf cannot be
// fetched in the development environment, so this cannot be compiled or tested
// here. Build and test it where the modules are available:
//
//	go get google.golang.org/grpc google.golang.org/protobuf
//	go test -tags=grpc -race ./internal/rpc/
//
// The generated stubs from proto/csc.proto are expected at gen/cscv1. Until this
// has actually run against a live server, no manifest may record rpc_type=grpc
// and the manuscript may not name gRPC.
package rpc

import (
	"context"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	cscv1 "github.com/TODO-OWNER/csc-iot/gen/cscv1"
)

type grpcClient struct {
	conn *grpc.ClientConn
	cli  cscv1.IntelligenceClient
	desc Descriptor
}

func DialGRPC(addr string, timeout time.Duration) (Client, error) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	conn, err := grpc.DialContext(ctx, addr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithBlock(),
	)
	if err != nil {
		return nil, err
	}
	return &grpcClient{
		conn: conn, cli: cscv1.NewIntelligenceClient(conn),
		desc: Descriptor{Type: "grpc", Version: grpc.Version, Address: addr},
	}, nil
}

func (g *grpcClient) EvaluateActions(ctx context.Context, req StateRequest) (ActionScores, Timing, error) {
	if _, ok := ctx.Deadline(); !ok {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, Deadline)
		defer cancel()
	}
	start := time.Now()
	resp, err := g.cli.EvaluateActions(ctx, toProto(req))
	rpcNanos := time.Since(start).Nanoseconds()
	if err != nil {
		return ActionScores{}, Timing{RPCNanos: rpcNanos, DeadlineMissed: true}, err
	}
	out := fromProto(resp)
	return out, Timing{
		RPCNanos:            rpcNanos - out.TModelNanos - out.TCounterfactualNanos,
		ModelNanos:          out.TModelNanos,
		CounterfactualNanos: out.TCounterfactualNanos,
	}, nil
}

func (g *grpcClient) Descriptor() Descriptor { return g.desc }

func (g *grpcClient) Close() error { return g.conn.Close() }

// toProto / fromProto are thin and deliberately lossless: the observational and
// interventional risks must remain distinct fields on the wire, as they are in
// the model and in the logs.
func toProto(r StateRequest) *cscv1.StateSnapshot {
	panic("implement against proto/csc.proto during local validation")
}
func fromProto(p *cscv1.ActionRanking) ActionScores {
	panic("implement against proto/csc.proto during local validation")
}
