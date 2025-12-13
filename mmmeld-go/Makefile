BINARY_NAME_MMMELD=mmmeld
BINARY_NAME_TTS=tts
BUILD_DIR=bin
INSTALL_DIR ?= /usr/local/bin

# OS-aware settings
OS := $(shell uname -s 2>/dev/null || echo Windows)
ifeq ($(OS),Windows)
	MKDIR_P=mkdir $(BUILD_DIR) 2> NUL || exit 0
	RM_RF=cmd /c rmdir /s /q $(BUILD_DIR) 2> NUL & del /q coverage.out coverage.html 2> NUL & rmdir /s /q temp_assets 2> NUL || exit 0
	SEP=\\
	EXEEXT=.exe
	RUN_PREFIX=
else
	MKDIR_P=mkdir -p $(BUILD_DIR)
	RM_RF=rm -rf $(BUILD_DIR) coverage.out coverage.html temp_assets
	SEP=/
	EXEEXT=
	RUN_PREFIX=./
endif

.PHONY: all build test clean run-mmmeld run-tts help

all: build test

build: build-mmmeld build-tts

build-mmmeld:
	@echo "Building mmmeld..."
	@$(MKDIR_P)
	@go build -o $(BUILD_DIR)$(SEP)$(BINARY_NAME_MMMELD)$(EXEEXT) ./cmd/mmmeld

build-tts:
	@echo "Building tts..."
	@$(MKDIR_P)
	@go build -o $(BUILD_DIR)$(SEP)$(BINARY_NAME_TTS)$(EXEEXT) ./cmd/tts

test:
	@echo "Running tests..."
	@go test -v ./...

test-coverage:
	@echo "Running tests with coverage..."
	@go test -v -coverprofile=coverage.out ./...
	@go tool cover -html=coverage.out -o coverage.html

clean:
	@echo "Cleaning up..."
	@$(RM_RF)

run-mmmeld: build-mmmeld
	@echo "Running mmmeld..."
	@$(RUN_PREFIX)$(BUILD_DIR)$(SEP)$(BINARY_NAME_MMMELD)$(EXEEXT)

run-tts: build-tts
	@echo "Running tts..."
	@$(RUN_PREFIX)$(BUILD_DIR)$(SEP)$(BINARY_NAME_TTS)$(EXEEXT)

install: build
	@echo "Installing binaries to $(INSTALL_DIR)..."
	@mkdir -p $(INSTALL_DIR)
	@cp $(BUILD_DIR)/$(BINARY_NAME_MMMELD) $(INSTALL_DIR)/
	@cp $(BUILD_DIR)/$(BINARY_NAME_TTS) $(INSTALL_DIR)/
	@echo "Installed to $(INSTALL_DIR). Make sure it's in your PATH."

fmt:
	@echo "Formatting code..."
	@go fmt ./...

vet:
	@echo "Running go vet..."
	@go vet ./...

lint:
	@echo "Running golint (if available)..."
	@command -v golint >/dev/null 2>&1 && golint ./... || echo "golint not available"

check: fmt vet lint test

help:
	@echo "Available commands:"
	@echo "  build         - Build both mmmeld and tts binaries"
	@echo "  build-mmmeld  - Build only mmmeld binary"
	@echo "  build-tts     - Build only tts binary"
	@echo "  test          - Run all tests"
	@echo "  test-coverage - Run tests with coverage report"
	@echo "  clean         - Clean build artifacts and temp files"
	@echo "  run-mmmeld    - Build and run mmmeld"
	@echo "  run-tts       - Build and run tts"
	@echo "  install       - Install binaries (default: /usr/local/bin, override with INSTALL_DIR)"
	@echo "  fmt           - Format Go code"
	@echo "  vet           - Run go vet"
	@echo "  lint          - Run golint"
	@echo "  check         - Run fmt, vet, lint, and test"
	@echo "  help          - Show this help message"
