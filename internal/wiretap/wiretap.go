// Package wiretap records the raw JSON-RPC messages flowing over an MCP
// connection as JSON Lines, one message per line.
//
// The output is used to capture golden fixtures (testdata/mcp/*.jsonl) that
// the Phase 2 proxy must relay byte-for-byte.
package wiretap

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"sync"

	"github.com/modelcontextprotocol/go-sdk/jsonrpc"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// Direction of a recorded message, from the point of view of the wrapped side.
const (
	Sent     = "sent"
	Received = "received"
)

// Record is one line of a wiretap capture.
type Record struct {
	Dir string          `json:"dir"`
	Msg json.RawMessage `json:"msg"`
}

// Transport wraps another transport and writes every message it sends or
// receives to W.
type Transport struct {
	Transport mcp.Transport
	W         io.Writer
}

// Connect implements mcp.Transport.
func (t *Transport) Connect(ctx context.Context) (mcp.Connection, error) {
	conn, err := t.Transport.Connect(ctx)
	if err != nil {
		return nil, err
	}
	return &tapConn{Connection: conn, w: t.W}, nil
}

type tapConn struct {
	mcp.Connection

	mu sync.Mutex
	w  io.Writer
}

func (c *tapConn) Read(ctx context.Context) (jsonrpc.Message, error) {
	msg, err := c.Connection.Read(ctx)
	if err == nil {
		c.record(Received, msg)
	}
	return msg, err
}

func (c *tapConn) Write(ctx context.Context, msg jsonrpc.Message) error {
	err := c.Connection.Write(ctx, msg)
	if err == nil {
		c.record(Sent, msg)
	}
	return err
}

func (c *tapConn) record(dir string, msg jsonrpc.Message) {
	data, err := jsonrpc.EncodeMessage(msg)
	if err != nil {
		data = fmt.Appendf(nil, "%q", "wiretap: encode failed: "+err.Error())
	}
	line, _ := json.Marshal(Record{Dir: dir, Msg: data})

	c.mu.Lock()
	defer c.mu.Unlock()
	_, _ = c.w.Write(append(line, '\n'))
}
