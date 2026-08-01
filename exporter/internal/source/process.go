package source

import (
	"encoding/csv"
	"fmt"
	"strings"
)

func easyWorshipInTasklist(output string) (bool, error) {
	rows, err := csv.NewReader(strings.NewReader(output)).ReadAll()
	if err != nil {
		return false, fmt.Errorf("parse tasklist output: %w", err)
	}
	for _, row := range rows {
		if len(row) > 0 && strings.EqualFold(row[0], "EasyWorship.exe") {
			return true, nil
		}
	}
	return false, nil
}
