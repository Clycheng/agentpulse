FROM golang:1.26.5-alpine@sha256:0178a641fbb4858c5f1b48e34bdaabe0350a330a1b1149aabd498d0699ff5fb2 AS builder

ARG CADDY_COMMIT=e2eee6a7fce366321294c9c2a79f3146891dcbdf

RUN apk add --no-cache ca-certificates git \
    && git init /src \
    && git -C /src remote add origin https://github.com/caddyserver/caddy.git \
    && git -C /src fetch --depth 1 origin "${CADDY_COMMIT}" \
    && git -C /src checkout --detach FETCH_HEAD \
    && test "$(git -C /src rev-parse HEAD)" = "${CADDY_COMMIT}"

WORKDIR /src
RUN go mod edit -require=google.golang.org/grpc@v1.82.1 \
    && go mod tidy \
    && CGO_ENABLED=0 go build \
        -buildvcs=false \
        -trimpath \
        -ldflags='-s -w -X github.com/caddyserver/caddy/v2.CustomVersion=v2.11.4-agentpulse.1' \
        -o /out/caddy \
        ./cmd/caddy

FROM alpine:3.23@sha256:fd791d74b68913cbb027c6546007b3f0d3bc45125f797758156952bc2d6daf40

RUN apk upgrade --no-cache \
    && apk add --no-cache ca-certificates \
    && addgroup -S caddy \
    && adduser -S -D -H -h /var/lib/caddy -s /sbin/nologin -G caddy caddy \
    && mkdir -p /config /data /etc/caddy \
    && chown -R caddy:caddy /config /data

COPY --from=builder /out/caddy /usr/bin/caddy

ENV XDG_CONFIG_HOME=/config \
    XDG_DATA_HOME=/data

USER caddy
EXPOSE 80 443 443/udp
ENTRYPOINT ["caddy"]
CMD ["run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
