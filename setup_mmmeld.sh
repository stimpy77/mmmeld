#!/bin/bash

# Get the directory of the current script
scriptDir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create the mmmeld.sh script
cat << 'EOF' > "$scriptDir/mmmeld.sh"
#!/bin/bash
if [ "$#" -eq 0 ]; then
    python "$scriptDir/mmmeld.py"
else
    python "$scriptDir/mmmeld.py" "$@"
fi
EOF

# Create the tts.sh script
cat << 'EOF' > "$scriptDir/tts.sh"
#!/bin/bash
if [ "$#" -eq 0 ]; then
    python "$scriptDir/tts.py"
else
    python "$scriptDir/tts.py" "$@"
fi
EOF

# Make the scripts executable
chmod +x "$scriptDir/mmmeld.sh"
chmod +x "$scriptDir/tts.sh"

# Create .local and .local/bin if they don't exist
localPath="$HOME/.local"
localBinPath="$localPath/bin"
mkdir -p "$localBinPath"

# Move the mmmeld.sh and tts.sh scripts to .local/bin
mv "$scriptDir/mmmeld.sh" "$localBinPath/mmmeld"
mv "$scriptDir/tts.sh" "$localBinPath/tts"

# Add .local/bin to PATH if it's not already there
if [[ ":$PATH:" != *":$localBinPath:"* ]]; then
    echo "export PATH=\"$localBinPath:\$PATH\"" >> "$HOME/.bashrc"
    export PATH="$localBinPath:$PATH"
    echo ".local/bin has been added to your PATH environment variable."
else
    echo ".local/bin is already in your PATH environment variable."
fi

echo "mmmeld and tts have been deployed. You may need to restart your shell session to use them immediately."
