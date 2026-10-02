package main

import (
	"context"
	"fmt"
	"strings"

	"github.com/modelcontextprotocol/go-sdk/mcp"

	"github.com/pun33t19/ledgerline/internal/demo"
)

// WeatherArgs mirrors the get_weather example in the Anthropic tool-use docs.
type WeatherArgs struct {
	Location string `json:"location" jsonschema:"The city and state, e.g. San Francisco, CA"`
	Unit     string `json:"unit,omitempty" jsonschema:"celsius or fahrenheit (default fahrenheit)"`
}

type reading struct {
	tempF      float64
	conditions string
}

// Canned data keeps the server deterministic and offline, so test fixtures
// never change between runs.
var readings = map[string]reading{
	"san francisco, ca": {61, "Fog"},
	"new york, ny":      {72, "Partly cloudy"},
	"pune, in":          {84, "Humid, light rain"},
}

func newServer() *mcp.Server {
	server := mcp.NewServer(&mcp.Implementation{Name: "weather", Version: "0.1.0"}, nil)
	mcp.AddTool(server, &mcp.Tool{
		Name:        "get_weather",
		Description: "Get the current weather in a given location",
		Annotations: &mcp.ToolAnnotations{ReadOnlyHint: true},
	}, getWeather)
	return server
}

func getWeather(_ context.Context, _ *mcp.CallToolRequest, args WeatherArgs) (*mcp.CallToolResult, any, error) {
	r, ok := readings[strings.ToLower(strings.TrimSpace(args.Location))]
	if !ok {
		res := demo.Text(fmt.Sprintf("No weather data for %q. Try San Francisco, CA; New York, NY; or Pune, IN.", args.Location))
		res.IsError = true
		return res, nil, nil
	}

	temp, symbol := r.tempF, "°F"
	switch strings.ToLower(args.Unit) {
	case "", "fahrenheit":
	case "celsius":
		temp, symbol = (r.tempF-32)*5/9, "°C"
	default:
		res := demo.Text(fmt.Sprintf("Unknown unit %q; use celsius or fahrenheit.", args.Unit))
		res.IsError = true
		return res, nil, nil
	}

	return demo.Text(fmt.Sprintf("Current weather in %s:\nTemperature: %.0f%s\nConditions: %s",
		args.Location, temp, symbol, r.conditions)), nil, nil
}
