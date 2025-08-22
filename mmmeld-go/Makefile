BINARY_NAME_MMMELD=mmmeld
BINARY_NAME_TTS=tts
BUILD_DIR=bin

.PHONY: all build test clean run-mmmeld run-tts help

all: build test

build: build-mmmeld build-tts

build-mmmeld:
	@echo "Building mmmeld..."
	@mkdir -p $(BUILD_DIR)
	@go build -o $(BUILD_DIR)/$(BINARY_NAME_MMMELD) ./cmd/mmmeld

build-tts:
	@echo "Building tts..."
	@mkdir -p $(BUILD_DIR)
	@go build -o $(BUILD_DIR)/$(BINARY_NAME_TTS) ./cmd/tts

test:
	@echo "Running tests..."
	@go test -v ./...

test-coverage:
	@echo "Running tests with coverage..."
	@go test -v -coverprofile=coverage.out ./...
	@go tool cover -html=coverage.out -o coverage.html

clean:
	@echo "Cleaning up..."
	@rm -rf $(BUILD_DIR)
	@rm -f coverage.out coverage.html
	@rm -rf temp_assets

run-mmmeld: build-mmmeld
	@echo "Running mmmeld..."
	@./$(BUILD_DIR)/$(BINARY_NAME_MMMELD)

run-tts: build-tts
	@echo "Running tts..."
	@./$(BUILD_DIR)/$(BINARY_NAME_TTS)

install: build
	@echo "Installing binaries to /usr/local/bin..."
	@sudo cp $(BUILD_DIR)/$(BINARY_NAME_MMMELD) /usr/local/bin/
	@sudo cp $(BUILD_DIR)/$(BINARY_NAME_TTS) /usr/local/bin/

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
	@echo "  install       - Install binaries to /usr/local/bin"
	@echo "  fmt           - Format Go code"
	@echo "  vet           - Run go vet"
	@echo "  lint          - Run golint"
	@echo "  check         - Run fmt, vet, lint, and test"
	@echo "  help          - Show this help message"