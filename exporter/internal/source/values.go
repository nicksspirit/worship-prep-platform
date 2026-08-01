package source

import (
	"encoding/base64"
	"fmt"

	"github.com/nicksspirit/worship-prep-platform/exporter/internal/contract"
)

func sourceValue(value any) contract.SourceValue {
	switch typed := value.(type) {
	case nil:
		return contract.SourceValue{Type: "null"}
	case int64:
		return contract.SourceValue{Type: "integer", Value: typed}
	case float64:
		return contract.SourceValue{Type: "real", Value: typed}
	case string:
		return contract.SourceValue{Type: "text", Value: typed}
	case []byte:
		return contract.SourceValue{
			Type:  "blob",
			Value: base64.StdEncoding.EncodeToString(typed),
		}
	default:
		return contract.SourceValue{Type: "unknown", Value: fmt.Sprint(typed)}
	}
}

func optionalString(value any) *string {
	if value == nil {
		return nil
	}
	text := fmt.Sprint(value)
	if text == "" {
		return nil
	}
	return &text
}
