// Command demo-client is a minimal MCP client for exercising the demo servers:
// initialize → tools/list → tools/call, optionally recording raw wire traffic.
//
//	demo-client [flags] -- <server command> [args...]   # stdio
//	demo-client [flags] --http http://localhost:8081    # Streamable HTTP
//
// After every call it re-lists the tools and reports any definition that
// changed, which is how you see a rug pull happen.
package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"maps"
	"os"
	"os/exec"
	"slices"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/pun33t19/ledgerline/internal/version"
	"github.com/pun33t19/ledgerline/internal/wiretap"
)

type options struct {
	httpURL string
	wire    string
	tool    string
	args    string
	repeat  int
	command []string
}

func main() {
	var o options
	flag.StringVar(&o.httpURL, "http", "", "connect to a Streamable HTTP server at this URL instead of spawning a command")
	flag.StringVar(&o.wire, "wire", "", "record raw JSON-RPC traffic to this JSONL file")
	flag.StringVar(&o.tool, "call", "", "tool to call (omit to only list tools)")
	flag.StringVar(&o.args, "args", "{}", "tool arguments as a JSON object")
	flag.IntVar(&o.repeat, "repeat", 1, "number of times to call the tool")
	flag.Usage = func() {
		fmt.Fprintf(flag.CommandLine.Output(), "usage: %s [flags] -- <server command> [args...]\n       %s [flags] --http <url>\n\n", os.Args[0], os.Args[0])
		flag.PrintDefaults()
	}
	flag.Parse()
	o.command = flag.Args()

	if err := run(context.Background(), o, os.Stdout); err != nil {
		log.Fatal(err)
	}
}

func run(ctx context.Context, o options, out io.Writer) (err error) {
	transport, err := transportFor(o)
	if err != nil {
		return err
	}
	if o.wire != "" {
		f, ferr := os.Create(o.wire) // not err: the deferred close must set the named return
		if ferr != nil {
			return ferr
		}
		// A failed close can mean lost capture data, so report it.
		defer func() { err = errors.Join(err, f.Close()) }()
		transport = &wiretap.Transport{Transport: transport, W: f}
	}

	var callArgs map[string]any
	if err := json.Unmarshal([]byte(o.args), &callArgs); err != nil {
		return fmt.Errorf("--args must be a JSON object: %w", err)
	}

	client := mcp.NewClient(&mcp.Implementation{Name: "ledgerline-demo-client", Version: version.String()}, nil)
	cs, err := client.Connect(ctx, transport, nil)
	if err != nil {
		return fmt.Errorf("connect: %w", err)
	}
	defer func() { _ = cs.Close() }()

	if init := cs.InitializeResult(); init != nil && init.ServerInfo != nil {
		fmt.Fprintf(out, "Connected to %s %s (protocol %s)\n", init.ServerInfo.Name, init.ServerInfo.Version, init.ProtocolVersion)
	}

	pinned, err := listTools(ctx, cs)
	if err != nil {
		return err
	}
	fmt.Fprintln(out, "\nTools:")
	for _, name := range sortedNames(pinned) {
		printTool(out, pinned[name])
	}

	if o.tool == "" {
		return nil
	}
	for i := 1; i <= o.repeat; i++ {
		res, err := cs.CallTool(ctx, &mcp.CallToolParams{Name: o.tool, Arguments: callArgs})
		if err != nil {
			return fmt.Errorf("call %d: %w", i, err)
		}
		fmt.Fprintf(out, "\nCall %d → %s%s\n", i, resultText(res), errSuffix(res))

		current, err := listTools(ctx, cs)
		if err != nil {
			return err
		}
		for _, name := range sortedNames(current) {
			if old, ok := pinned[name]; ok && old.hash != current[name].hash {
				fmt.Fprintf(out, "\n⚠ Tool %q changed after call %d (sha256 %s → %s). New definition:\n", name, i, old.hash[:12], current[name].hash[:12])
				printTool(out, current[name])
			}
		}
		pinned = current
	}
	return nil
}

func transportFor(o options) (mcp.Transport, error) {
	switch {
	case o.httpURL != "" && len(o.command) > 0:
		return nil, errors.New("use either --http or a server command, not both")
	case o.httpURL != "":
		return &mcp.StreamableClientTransport{Endpoint: o.httpURL}, nil
	case len(o.command) > 0:
		cmd := exec.Command(o.command[0], o.command[1:]...) //nolint:gosec // the user chooses which demo server to run
		cmd.Stderr = os.Stderr
		return &mcp.CommandTransport{Command: cmd}, nil
	default:
		return nil, errors.New("give a server command after -- or use --http (see -h)")
	}
}

type toolInfo struct {
	tool *mcp.Tool
	// hash is a preview of Phase 2 pinning. It uses encoding/json, which is
	// not canonical (RFC 8785); Phase 2 replaces it with JCS.
	hash string
}

func listTools(ctx context.Context, cs *mcp.ClientSession) (map[string]toolInfo, error) {
	tools := map[string]toolInfo{}
	for tool, err := range cs.Tools(ctx, nil) {
		if err != nil {
			return nil, fmt.Errorf("tools/list: %w", err)
		}
		data, err := json.Marshal(tool)
		if err != nil {
			return nil, err
		}
		sum := sha256.Sum256(data)
		tools[tool.Name] = toolInfo{tool: tool, hash: hex.EncodeToString(sum[:])}
	}
	return tools, nil
}

func printTool(out io.Writer, t toolInfo) {
	fmt.Fprintf(out, "- %s  [sha256 %s]\n", t.tool.Name, t.hash[:12])
	for line := range strings.SplitSeq(t.tool.Description, "\n") {
		fmt.Fprintf(out, "    │ %s\n", line)
	}
}

func resultText(res *mcp.CallToolResult) string {
	var parts []string
	for _, c := range res.Content {
		if tc, ok := c.(*mcp.TextContent); ok {
			parts = append(parts, tc.Text)
		}
	}
	return strings.ReplaceAll(strings.Join(parts, " "), "\n", " | ")
}

func errSuffix(res *mcp.CallToolResult) string {
	if res.IsError {
		return "  (isError)"
	}
	return ""
}

func sortedNames(m map[string]toolInfo) []string {
	return slices.Sorted(maps.Keys(m))
}
