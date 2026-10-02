package wiretap

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"testing"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func TestTransportRecordsBothDirections(t *testing.T) {
	ctx := context.Background()

	server := mcp.NewServer(&mcp.Implementation{Name: "echo"}, nil)
	type args struct {
		Text string `json:"text"`
	}
	mcp.AddTool(server, &mcp.Tool{Name: "echo", Description: "echo text"},
		func(_ context.Context, _ *mcp.CallToolRequest, a args) (*mcp.CallToolResult, any, error) {
			return &mcp.CallToolResult{Content: []mcp.Content{&mcp.TextContent{Text: a.Text}}}, nil, nil
		})

	ct, st := mcp.NewInMemoryTransports()
	if _, err := server.Connect(ctx, st, nil); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	client := mcp.NewClient(&mcp.Implementation{Name: "test"}, nil)
	cs, err := client.Connect(ctx, &Transport{Transport: ct, W: &buf}, nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := cs.CallTool(ctx, &mcp.CallToolParams{Name: "echo", Arguments: map[string]any{"text": "hi"}}); err != nil {
		t.Fatal(err)
	}
	_ = cs.Close()

	var sent, received int
	var sawCall bool
	sc := bufio.NewScanner(&buf)
	for sc.Scan() {
		var r Record
		if err := json.Unmarshal(sc.Bytes(), &r); err != nil {
			t.Fatalf("line is not a Record: %v: %s", err, sc.Text())
		}
		var m struct {
			Method string `json:"method"`
		}
		_ = json.Unmarshal(r.Msg, &m)
		switch r.Dir {
		case Sent:
			sent++
			if m.Method == "tools/call" {
				sawCall = true
			}
		case Received:
			received++
		default:
			t.Errorf("unexpected dir %q", r.Dir)
		}
	}
	if sent == 0 || received == 0 {
		t.Fatalf("sent=%d received=%d, want both > 0", sent, received)
	}
	if !sawCall {
		t.Error("tools/call request was not recorded")
	}
}
