package ffmpeg

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"os/exec"
	"strings"
	"time"
)

// logFFmpeg logs ffmpeg output with clean formatting (no file/line info)
func logFFmpeg(message string) {
	fmt.Fprintf(os.Stderr, "%s [ffmpeg] %s\n", time.Now().Format("2006/01/02 15:04:05"), message)
}

// RunCommand executes an ffmpeg command with real-time progress output
func RunCommand(cmd []string) error {
	log.Printf("Running ffmpeg: %s", strings.Join(cmd, " "))
	
	execCmd := exec.Command(cmd[0], cmd[1:]...)
	
	// Create pipes for stdout and stderr
	stdout, err := execCmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("failed to create stdout pipe: %w", err)
	}
	
	stderr, err := execCmd.StderrPipe()
	if err != nil {
		return fmt.Errorf("failed to create stderr pipe: %w", err)
	}
	
	// Start the command
	if err := execCmd.Start(); err != nil {
		return fmt.Errorf("failed to start ffmpeg: %w", err)
	}
	
	// Create a channel to signal when output reading is done
	done := make(chan bool, 2)
	
	// Read stdout in a goroutine
	go func() {
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			line := scanner.Text()
			logFFmpeg(fmt.Sprintf("stdout: %s", line))
		}
		done <- true
	}()
	
	// Read stderr in a goroutine (ffmpeg outputs progress here)
	go func() {
		reader := bufio.NewReader(stderr)
		buffer := make([]byte, 4096)
		lineBuffer := make([]byte, 0, 4096)
		
		for {
			n, err := reader.Read(buffer)
			if n > 0 {
				for i := 0; i < n; i++ {
					if buffer[i] == '\r' {
						// Handle \r (carriage return) - used for progress updates
						if len(lineBuffer) > 0 {
							line := string(lineBuffer)
							logFFmpeg(line)
							lineBuffer = lineBuffer[:0]
						}
					} else if buffer[i] == '\n' {
						// Handle \n (newline) - creates a new line
						if len(lineBuffer) > 0 {
							line := string(lineBuffer)
							logFFmpeg(line)
							lineBuffer = lineBuffer[:0]
						}
					} else {
						lineBuffer = append(lineBuffer, buffer[i])
					}
				}
			}
			if err != nil {
				if len(lineBuffer) > 0 {
					line := string(lineBuffer)
					log.Printf("[ffmpeg] %s", line)
				}
				break
			}
		}
		done <- true
	}()
	
	// Wait for both output readers to finish
	<-done
	<-done
	
	// Wait for the command to complete
	if err := execCmd.Wait(); err != nil {
		return fmt.Errorf("ffmpeg failed: %w", err)
	}
	
	log.Println("ffmpeg command completed successfully")
	return nil
}

// RunCommandQuiet executes an ffmpeg command without progress output (for validation checks)
func RunCommandQuiet(cmd []string) error {
	execCmd := exec.Command(cmd[0], cmd[1:]...)
	if err := execCmd.Run(); err != nil {
		return err
	}
	return nil
}

// RunCommandWithOutput executes an ffmpeg command and returns the combined output
func RunCommandWithOutput(cmd []string) ([]byte, error) {
	execCmd := exec.Command(cmd[0], cmd[1:]...)
	return execCmd.CombinedOutput()
}