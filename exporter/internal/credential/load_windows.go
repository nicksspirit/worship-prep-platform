//go:build windows

// Package credential loads the Integration Client key protected for one Windows user.
package credential

import (
	"fmt"
	"os"
	"strings"
	"syscall"
	"unsafe"
)

const cryptprotectUIForbidden = 0x1

var (
	crypt32            = syscall.NewLazyDLL("Crypt32.dll")
	cryptUnprotectData = crypt32.NewProc("CryptUnprotectData")
	kernel32           = syscall.NewLazyDLL("Kernel32.dll")
	localFree          = kernel32.NewProc("LocalFree")
)

type dataBlob struct {
	size uint32
	data *byte
}

// Load decrypts a user-scoped Windows DPAPI credential file.
func Load(path string) (string, error) {
	protected, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("read protected API key: %w", err)
	}
	if len(protected) == 0 {
		return "", fmt.Errorf("protected API key is empty")
	}
	input := dataBlob{size: uint32(len(protected)), data: &protected[0]}
	var output dataBlob
	result, _, callErr := cryptUnprotectData.Call(
		uintptr(unsafe.Pointer(&input)),
		0,
		0,
		0,
		0,
		cryptprotectUIForbidden,
		uintptr(unsafe.Pointer(&output)),
	)
	if result == 0 {
		return "", fmt.Errorf("decrypt API key with current Windows user: %w", callErr)
	}
	defer localFree.Call(uintptr(unsafe.Pointer(output.data)))
	plaintext := unsafe.Slice(output.data, output.size)
	apiKey := strings.TrimSpace(string(plaintext))
	if apiKey == "" {
		return "", fmt.Errorf("decrypted API key is empty")
	}
	return apiKey, nil
}
