// Command weather is a well-behaved demo MCP server with a single
// get_weather tool backed by canned data. It is the "honest" baseline that the
// Ledgerline proxy must relay without changing anything.
//
//	weather              # stdio
//	weather --http :8081 # Streamable HTTP (stateless, protocol 2026-07-28)
//	weather --http :8081 --stateful  # legacy sessions (protocol 2025-11-25)
package main

import (
	"flag"
	"log"

	"github.com/pun33t19/ledgerline/internal/demo"
)

func main() {
	var transport demo.Transport
	transport.RegisterFlags(flag.CommandLine)
	flag.Parse()

	if err := demo.Serve(newServer(), transport); err != nil {
		log.Fatal(err)
	}
}
