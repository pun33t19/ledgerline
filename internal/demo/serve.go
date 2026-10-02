// Package demo holds helpers shared by the demo MCP servers in cmd/demo-servers.
// None of this code is part of Ledgerline itself.
package demo

import (
	"context"
	"errors"
	"flag"
	"log"
	"net/http"
	"os/signal"
	"syscall"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// Transport selects how a demo server is exposed.
type Transport struct {
	// HTTPAddr serves Streamable HTTP on this address; empty means stdio.
	HTTPAddr string
	// Stateful uses the legacy session-based HTTP mode. The SDK only offers
	// protocol 2026-07-28 (server/discover, Mcp-Method/Mcp-Name headers) in
	// stateless mode, so stateful servers negotiate 2025-11-25 via initialize.
	Stateful bool
}

// RegisterFlags adds the shared -http and -stateful flags.
func (t *Transport) RegisterFlags(fs *flag.FlagSet) {
	fs.StringVar(&t.HTTPAddr, "http", "", "serve Streamable HTTP on this address instead of stdio")
	fs.BoolVar(&t.Stateful, "stateful", false, "with -http, use legacy stateful sessions (protocol 2025-11-25)")
}

// Serve runs server over stdio or Streamable HTTP, as t selects.
// It returns when stdin closes, the HTTP server stops, or SIGINT/SIGTERM arrives.
func Serve(server *mcp.Server, t Transport) error {
	httpAddr := t.HTTPAddr
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	if httpAddr == "" {
		return server.Run(ctx, &mcp.StdioTransport{})
	}

	handler := mcp.NewStreamableHTTPHandler(func(*http.Request) *mcp.Server { return server }, &mcp.StreamableHTTPOptions{Stateless: !t.Stateful})
	srv := &http.Server{Addr: httpAddr, Handler: handler, ReadHeaderTimeout: 5 * time.Second}

	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = srv.Shutdown(shutdownCtx)
	}()

	// Logs go to stderr so they never mix with stdio protocol traffic.
	log.Printf("MCP server listening on http://%s", httpAddr)
	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		return err
	}
	return nil
}

// Text builds a single-text-block tool result.
func Text(s string) *mcp.CallToolResult {
	return &mcp.CallToolResult{Content: []mcp.Content{&mcp.TextContent{Text: s}}}
}
