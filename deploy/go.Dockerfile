# NOTE: this file is deliberately NOT named Dockerfile.go.
# A file ending in .go is treated by the Go tool as a source file, and
# `go test ./...` fails with 'illegal character U+0023' before it reaches
# a single test. Cheap mistake, confusing symptom.
#
# One image, one binary, selected at build time by CMD_NAME.
#
# GO_VERSION must satisfy the `go` directive in go.mod. `go get` rewrites that
# directive to whatever toolchain ran it -- running `make deps-adapters` on a
# machine with Go 1.26 set `go 1.26.0`, and a 1.23 base image then failed inside
# `go build` with an error that looked like a code problem and was not.
# GOTOOLCHAIN=auto lets the image fetch a newer toolchain if the directive moves
# again, so the build survives the next `go get` without an edit here.
ARG GO_VERSION=1.26
FROM golang:${GO_VERSION}-alpine AS build
ENV GOTOOLCHAIN=auto
ARG CMD_NAME
# GO_TAGS selects optional adapters. Empty is the development build; "nats"
# compiles the NATS transport in. A binary built without it cannot silently fall
# back to the development bus -- bus.Dial refuses the unknown transport by name.
ARG GO_TAGS=""
WORKDIR /src

# go.sum must be copied too: with module requirements present and no go.sum,
# `go build` fails on verification even for packages behind build tags.
COPY go.mod go.sum ./
RUN go mod download

COPY cmd ./cmd
COPY internal ./internal
RUN test -n "$CMD_NAME" || (echo "CMD_NAME build-arg is required" && exit 1)
RUN CGO_ENABLED=0 go build -trimpath -tags "${GO_TAGS}" -o /out/app ./cmd/${CMD_NAME}

FROM alpine:3.20
# iproute2: the fault injector applies tc/netem inside the container on its own
# interface. On macOS the Docker bridges live inside a VM the host cannot
# address, so per-container application is the portable form and behaves
# identically on Linux.
RUN apk add --no-cache iproute2 ca-certificates
COPY --from=build /out/app /usr/local/bin/app
ENTRYPOINT ["/usr/local/bin/app"]
